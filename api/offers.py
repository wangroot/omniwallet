import urlparse
import os, sys, tempfile, json
import glob,time
tools_dir = os.environ.get('TOOLSDIR')
lib_path = os.path.abspath(tools_dir)
sys.path.append(lib_path)
from msc_apps import *
from decimal import *

sqlconn = sql_connect()
data_dir_root = os.environ.get('DATADIR')

def offers_response(response_dict):
    expected_fields=['type','currencyType']
    for field in expected_fields:
        if not response_dict.has_key(field):
            return (None, 'No field '+field+' in response dict '+str(response_dict))
        if len(response_dict[field]) != 1:
            return (None, 'Multiple values for field '+field)
    
    if response_dict['type'][0].upper() == "TIME":
        time = int(response_dict['time'][0]) if 'time' in response_dict else 86400
        data = filterOffersByTime( response_dict['currencyType'][0] , time  )
    else:
        address_arr = json.loads(response_dict['address'][0])
        data = filterOffers(address_arr) if type( address_arr ) == type( [] ) else { 'ERR': 'Address field must be a list or array type' } 
    
    response_status='OK'
    response='{"status":"'+response_status+'", "data":'+ str(json.dumps(data)) +'}'
    
    return (response, None)

def filterOffersByTime( currency_type , time_seconds):
    #filter by currency
    currency = ('1' if currency_type == 'MSC' else '2')

    atleast_now = int( str( int(time.time() - time_seconds) ) + '000' )

    #TODO get inactive offers?
    sqlconn.execute("select * from activeoffers ao, transactions t, txjson tj where ao.propertyidselling=" + currency + " and ao.lasttxdbserialnum=-1 and ao.createtxdbserialnum=t.txdbserialnum and ao.createtxdbserialnum=tj.txdbserialnum")
    ROWS= sqlconn.fetchall()

    response = [ mapSchema(row) for row in ROWS if int(mapSchema(row)['tx_time']) > atleast_now ]

    return sorted(response, key=lambda x:  int(x['tx_time']) )
    
def mapSchema(row):
  print row
  rawdata = row[-1]

  #We only map tx21 and tx22
  if row[-11] == 20:
    response = {
      'action': -1, #don't have this data
      'block': str(row[-5]),
      'currencyId': str(rawdata['propertyid']),
      'currency_str': 'Mastercoin' if str(rawdata['propertyid']) == '1' else 'Test Mastercoin',
      'formatted_amount': str(rawdata['amount']),
      'formatted_amount_available': str( row[1] / Decimal(1e8) ),
      'formatted_bitcoin_amount_desired': str( row[2] / Decimal(1e8) ),
      'formatted_block_time_limit': str(rawdata['timelimit']),
      'formatted_fee_required': str(rawdata['feerequired']),
      'formatted_price_per_coin': str( Decimal( rawdata['bitcoindesired'] ) / Decimal( rawdata['amount'] ) ),
      'from_address': rawdata['sendingaddress'],
      'tx_type_str': "Sell offer",
      'color': "bgc-new", #TODO fix
      'invalid': False if rawdata['valid'] == True else True,
      'to_address': "sell offer",
      'tx_hash': rawdata['txid'],
      'tx_time': str(rawdata['blocktime']) + '000'
    }
  else:
    response = {
      'block': str(row[-5]),
      'currencyId': str(rawdata['propertyid']),
      'currency_str': 'Mastercoin' if str(rawdata['propertyid']) == '1' else 'Test Mastercoin',
      'formatted_amount': str(rawdata['amount']),
      'formatted_amount_available': str( row[1] / Decimal(1e8) ),
      'formatted_bitcoin_amount_desired': str( row[2] / Decimal(1e8) ),
      #'formatted_fee_required': str(rawdata['feerequired']),
      #'formatted_price_per_coin': str( Decimal( rawdata['bitcoindesired'] ) / Decimal( rawdata['amount'] ) ),
      'from_address': rawdata['sendingaddress'],
      'tx_type_str': 'Sell accept',
      'color': "bgc-new", #TODO fix
      #'invalid': False if rawdata['valid'] == True else True,
      'to_address': 'TODO', #TODO fix
      'tx_hash': rawdata['txid'],
      'tx_time': str(rawdata['blocktime']) + '000'
    }

  #keys that might be useful later
  #bitcoin_amount_desired: "00000000002625a0"
  #block_time_limit: "0f"
  #index: "884"
  #icon: "selloffer"
  #icon_text: "Sell offer done"
  
  return response

def genQs(prefix, tbl_abbr, field, array):
    qs = '(' + tbl_abbr + '.' + field + '=\'' + array[0] + '\' '
    for entry in array[1:]:
      entry = re.sub(r'\W+', '', entry) #check alphanumeric
      qs += prefix + ' ' + tbl_abbr + '.' + field + '=\'' + entry +'\' '
    return qs + ') '

def filterOffers(addresses):
    #Returns all *ACTIVE* accepts and offers for a given address
    offers = {}
    
    #Query all active offers
    qs = genQs('or', 'ao', 'seller', addresses)

    query= "select * from activeoffers ao, " + \
           "transactions t, txjson txj where " + qs + \
           "and offerstate='active' and ao.createtxdbserialnum=t.txdbserialnum " + \
           "and ao.createtxdbserialnum=txj.txdbserialnum"
    sqlconn.execute(query)
    ROWS= sqlconn.fetchall()

    print query

    for row in ROWS:
      print row
      address = row[-1]['sendingaddress']
      currency = 'MSC' if row[-1]['propertyid'] == 1 else 'TMSC'

      if address not in offers: offers[ address ] = {}
      if 'offer_tx' not in offers[ address ]: offers[ address ]['offer_tx'] = {}
      
      offers[ address ]['offer_tx'][ currency ] = mapSchema(row)
      #only one active offer per address

    #Query all active accepts
    qs = genQs('or', 'oa', 'buyer', addresses)
    query= "select * from offeraccepts oa, " + \
           "transactions t, txjson txj where " + qs + \
           "and expiredstate='f' and oa.linkedtxdbserialnum=t.txdbserialnum " + \
           "and oa.linkedtxdbserialnum=txj.txdbserialnum"
    sqlconn.execute(query)
    ROWS= sqlconn.fetchall()

    print query

    for row in ROWS:
      print row
      address = row[-1]['referenceaddress']
      currency = 'MSC' if row[-1]['propertyid'] == 1 else 'TMSC'

      if address not in offers: offers[ address ] = {}
      if 'accept_tx' not in offers[ address ]: offers[ address ]['accept_tx'] = {}

      offers[ address ]['accept_tx'][ currency ] = mapSchema(row)
      #only one active offer per address

    return offers

def offers_handler(environ, start_response):
    return general_handler(environ, start_response, offers_response)
