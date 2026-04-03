import hmac
import hashlib
import requests
import time
import urllib.parse
from dotenv import load_dotenv
import os
import math
load_dotenv()

# Binance API credentials
API_KEY = os.getenv("BINANCE_API")
API_SECRET = os.getenv("BINANCE_SECRET")
BASE_URL = 'https://api.binance.com'

headers = {'X-MBX-APIKEY': API_KEY}




def get_margin_account(): #<--------------------- Segéd függvény. Meg tudod vizsgálni miből mennyi van a fiókon (mérmint coin)
    # Ensure correct timestamp
    timestamp = int(time.time() * 1000)

    # Sign the request
    query_string = f"timestamp={timestamp}"
    signature = hmac.new(
        API_SECRET.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    # Make the request
    url = f"{BASE_URL}/sapi/v1/margin/account?{query_string}&signature={signature}"
    headers = {'X-MBX-APIKEY': API_KEY}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()

        # Filter assets with non-zero free or borrowed balances
        filtered_assets = [
            {
                "asset": asset["asset"],
                "free": float(asset["free"]),
                "borrowed": float(asset["borrowed"])
            }
            for asset in data.get("userAssets", [])
            if float(asset["free"]) > 0 or float(asset["borrowed"]) > 0
        ]

        return filtered_assets
    else:
        # Handle errors
        print("Error:", response.status_code, response.text)
        return None


def get_min_trade_amount(symbol):#<----------Elég beszédes a neve.          SOLUSDC vagy valami hasonló!!!!!! Simán 'SOL'-ra akkor error message-t ad hogy beszarsz
    # Ensure correct timestamp
    timestamp = int(time.time() * 1000)

    # Make the request to get exchange info
    url = f"{BASE_URL}/api/v3/exchangeInfo"
    headers = {'X-MBX-APIKEY': API_KEY}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()

        # Find the symbol in the exchange info
        for symbol_info in data.get("symbols", []):
            if symbol_info["symbol"] == symbol:
                # Extract the LOT_SIZE filter for minimum trade amount
                for filter_info in symbol_info["filters"]:
                    if filter_info["filterType"] == "LOT_SIZE":
                        return float(filter_info["minQty"])

    # Return None if symbol not found or error occurs
    print("Symbol not found or error occurred. Status code:", response.status_code, "Response:", response.text)
    return None



def round_up_to_fraction(number, fraction): #<------------------ Ezek csak segítenek kerekítésekben.
    return math.ceil(number / fraction) * fraction

def round_down_to_fraction(number, fraction):
    return math.floor(number / fraction) * fraction

def round_down(number, ndigits):
    """
    Rounds down (toward -infinity) the given number to the specified number of decimal places.

    Parameters:
        number (float): The number to round down.
        ndigits (int): The number of decimal places.

    Returns:
        float: The rounded-down value.

    Example:
        round_down(4.567, 2) -> 4.56
        round_down(-4.567, 2) -> -4.57
    """
    factor = 10 ** ndigits
    return math.floor(number * factor) / factor


def get_coin_balance(coin_label):#<------ Vissza adja egy tuple-ben hogy mennyi van az adott currency-ből.  !FONTOS! Ez viszont olyat szeretne mint 'SOL', nem 'SOLUSDC', arra nem lesz találat. Többi részlet elég egyértelmű
    assets = get_margin_account()

    if assets is not None:
        for asset in assets:
            if asset["asset"] == coin_label:
                return (asset["free"], asset["borrowed"])

    # Return (0.0, 0.0) if the coin is not found or no assets
    return (0.0, 0.0)


def sign_request(params):#<---------------- Ez az egyik legfontosabb Helper Function, enélkül egyik eladós/vevős function sem megy.
    query_string = '&'.join([f"{key}={value}" for key, value in params.items()])
    signature = hmac.new(
        API_SECRET.encode('utf-8'), 
        query_string.encode('utf-8'), 
        hashlib.sha256
    ).hexdigest()
    return f"{query_string}&signature={signature}"

#--------------------------------------------------

def place_margin_trade(symbol, side, quantity): #<---------------- Ez arra az esetre van, ha margin trade-elni akarna valaki, és a kód futása közben változtatni, hogy ott eladjon vagy vegyen. A side legyen BUY vagy SELL.
    params = {
        'symbol': symbol,
        'side': side,                           # 'BUY' or 'SELL'
        'type': 'MARKET',                       # Use market order
        'quantity': quantity,                   # Amount to trade
        'isIsolated': 'FALSE',                  # Ensure this is a cross margin trade
        'timestamp': int(time.time() * 1000)
    }
    query_string = sign_request(params)
    response = requests.post(f"{BASE_URL}/sapi/v1/margin/order?{query_string}", headers=headers)
    print(f"Trade Response: {response.json()}")


def place_custom_margin_trade(symbol, side, type, quantity, isIsolated ='FALSE'): #<---------------- Itt minden amit meg akarhat valaki változtatni, megváltoztatható.
    params = {
        'symbol': symbol,                       # Ez elég egyértelmű. 'SOLUSDC' és barátai. (Simán 'SOL' ide sem elég)
        'side': side,                           # 'BUY' vagy 'SELL'
        'type': type,                           # 'MARKET' vagy 'LIMIT'
        'quantity': quantity,                   # Mennyit akarsz trade-elni? Ez NEM USD-ben van, hanem az adott coin értékében. Tehát BITCOIN esetén a 0.01 az NEM 1 cent
        'isIsolated': isIsolated,               # Ez vagy 'FALSE' vagy 'TRUE'. Ezt őszintén nem értettem meg teljsen, de itt a magyarázat: 'TRUE': The trade is isolated, meaning the margin is specific to this symbol. 'FALSE': The trade is cross margin, meaning the margin is shared across all symbols.
        'timestamp': int(time.time() * 1000)    # Ehhez még a custom function-be se nyúlj
    }
    query_string = sign_request(params)
    response = requests.post(f"{BASE_URL}/sapi/v1/margin/order?{query_string}", headers=headers)
    print(f"Trade Response: {response.json()}")



def margin_sell(symbol, quantity): #<------------------- EZ a teljesen leegyszerűsített SELL. Csak mond meg neki, miből mennyit. Symbol az olyan mint 'SOLUSDC' nem csak 'SOL' simán
    params = {
        'symbol': symbol,
        'side': 'SELL',                         # 'BUY' or 'SELL'
        'type': 'MARKET',                       # Use market order
        'quantity': quantity,                   # Amount to trade
        'isIsolated': 'FALSE',                  # Ensure this is a cross margin trade
        'timestamp': int(time.time() * 1000)
    }
    query_string = sign_request(params)
    response = requests.post(f"{BASE_URL}/sapi/v1/margin/order?{query_string}", headers=headers)
    print(f"Trade Response: {response.json()}")


def margin_buy(symbol, quantity): #<------------------- EZ a teljesen leegyszerűsített BUY. Csak mond meg neki, miből mennyit. Symbol az olyan mint 'SOLUSDC' nem csak 'SOL' simán
    params = {
        'symbol': symbol,
        'side': 'BUY',                          # 'BUY' or 'SELL'
        'type': 'MARKET',                       # Use market order
        'quantity': quantity,                   # Amount to trade
        'isIsolated': 'FALSE',                  # Ensure this is a cross margin trade
        'timestamp': int(time.time() * 1000)
    }
    query_string = sign_request(params)
    #print(f"{BASE_URL}/sapi/v1/margin/order?{query_string}")
    response = requests.post(f"{BASE_URL}/sapi/v1/margin/order?{query_string}", headers=headers)
    print(f"Trade Response: {response.json()}")


# Innentől shorting.


def open_short(symbol, quantity):#<------------- Borrow a Short elkezdésére           !!!NAGYON FONTOS!!!         Ez olyat szeretne mint 'SOL' NEM olyat mint 'SOLUSDC'
    borrow_params = {
        'asset': symbol,
        'amount': quantity,
        'timestamp': int(time.time() * 1000)
    }
    borrow_url = f"{BASE_URL}/sapi/v1/margin/loan"
    borrow_response = requests.post(f"{borrow_url}?{sign_request(borrow_params)}", headers=headers)
    print(f"Borrow Response: {borrow_response.json()}")

def close_short(symbol, quantity, stablecoin='USDC'):#<------------------ Visszafizeti a short elején felvett coin-t.           !!!NAGYON FONTOS!!!         Ez olyat szeretne mint 'SOL' NEM olyat mint 'SOLUSDC'. Stablecoin az esetek 99%-ban ne legyen megváltoztatva
    (free, borrowed) = get_coin_balance(symbol)
    minTrade = get_min_trade_amount(f"{symbol}{stablecoin}")
    if free < borrowed:
        difference = round_up_to_fraction(borrowed - free, minTrade)
        place_margin_trade(f"{symbol}{stablecoin}", 'BUY', f"{max(difference, minTrade)}")#Idáig le ellenőzi hogy mennyit tud vissza fizetni. Máté kérésére az összesset vissza akarja fizetni.
    repay_params = {
        'asset': symbol,
        'amount': quantity,
        'timestamp': int(time.time() * 1000)
    }
    repay_url = f"{BASE_URL}/sapi/v1/margin/repay"
    repay_response = requests.post(f"{repay_url}?{sign_request(repay_params)}", headers=headers)
    print(f"Repay Response: {repay_response.json()}")

    (free, borrowed) = get_coin_balance(symbol)
    bonus = round_down_to_fraction(free, minTrade)
    if bonus > 0:
        place_margin_trade(f'{symbol}{stablecoin}', 'SELL', f"{bonus}")# Máté kéréséere magától dollárra váltja a profitot a bezáró fügvény.


def dumb_close_short(symbol, quantity):#<------------------ Visszafizeti a short elején felvett coin-t.           !!!NAGYON FONTOS!!!         Ez olyat szeretne mint 'SOL' NEM olyat mint 'SOLUSDC'. Stablecoin az esetek 99%-ban ne legyen megváltoztatva
    repay_params = {
        'asset': symbol,
        'amount': quantity,
        'timestamp': int(time.time() * 1000)
    }
    repay_url = f"{BASE_URL}/sapi/v1/margin/repay"
    repay_response = requests.post(f"{repay_url}?{sign_request(repay_params)}", headers=headers)
    print(f"Repay Response: {repay_response.json()}")


#<----------------- Innen nem short-olós függvény jön

def get_coin_quantity_for_usd(coin_label, usd_value, stableCoin = 'USDC'):
    """
    Kiszámolja mennyi coin-t tudsz venni X USD-ért (vagy ami a stable coin)

    :param coin_label: The coin symbol (e.g., 'BTC', 'ETH', 'SOL').
    :param usd_value: The amount of USD you want to spend.
    :param stableCoin: The stablecoin to use for pricing (default is 'USDC').
    :return: The quantity of the coin you can buy, or None if an error occurs.
    """
    # Step 1: Elkéri a coin értéket
    symbol = f"{coin_label}{stableCoin}"
    url = f"{BASE_URL}/api/v3/ticker/price?symbol={symbol}"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        coin_price = float(data['price'])  # Jelenlegi ára a coin-nak a stable coin-ban
        print(f"Current price of {coin_label}: {coin_price} {stableCoin}") #<--------------------------------------------------------------------------EZT COMMENT-ELD ha nem akarsz print-et.

        # Step 2: Kiszámolja mennyit tudsz venni.
        quantity = usd_value / coin_price
        return quantity
    else:
        # Handle errors
        print(f"Error fetching price for {coin_label}: {response.status_code}, {response.text}")
        return None



def get_conversion_value(from_coin, to_coin, amount, stableCoin = 'USDC'): #Ez a function megmondja, hogy egy adott coin mennyit érne egy másik ként.
    """
    Converts an amount of one cryptocurrency to its equivalent value in another cryptocurrency.
    Returns None if conversion fails.
    """
    # Direct conversio-val próbálkozik
    direct_symbol = f"{from_coin}{to_coin}"
    response = requests.get(f"{BASE_URL}/api/v3/ticker/price?symbol={direct_symbol}", headers=headers)
    
    if response.status_code == 200:
        price = float(response.json()['price'])
        return amount * price
    
    # Ha nincs direkt, megpróbálja fordítva megnézni
    reverse_symbol = f"{to_coin}{from_coin}"
    response = requests.get(f"{BASE_URL}/api/v3/ticker/price?symbol={reverse_symbol}", headers=headers)
    
    if response.status_code == 200:
        price = float(response.json()['price'])
        return amount / price
    
    # Ha egyik előző sincs, akkor convertálja stable coin-ba, és azzal próbálkozik.
    from_usdt = get_coin_quantity_for_usd(from_coin, 1, stableCoin)
    to_usdt = get_coin_quantity_for_usd(to_coin, 1, stableCoin)
    
    if from_usdt and to_usdt:
        return (amount * from_usdt) / to_usdt
    
    print(f"No conversion path found between {from_coin} and {to_coin}")
    return None



#---------------------------------------------------Giga Máté fügvény Discrod Bot-hoz
def percentage_based_allocation(orderList, stableCoin = 'USDC'): # Úgy kell megadni a bemeneti parancsot mint: [["BTC", 50], ["ETH", 10], ["SOL", 10]] #Listában listák. A belső listák első eleme a coin label, a második a %-os mennyiség. A nagy listában elgyen benne az összes elem, de ne haladja meg a 100%-ot. Minden extra el nem költött százalék USDC-be fog menni. NE adj meg neki stableCoint a listában.
    rounding = 5 #Ez százalékban van megadva. NE állítsd nullára
    sum = 0
    for i in orderList:
        sum += i[1]
    if sum > 98:
        return "Error, össz százalék meghaldta a 98-at."
    

    assetsOnAccount = get_margin_account() #Ez a része váltja stableCoin-ba a teljes fiókot.
    assetsOnAccountByDollar = []
    for i in assetsOnAccount:
        if i["asset"] == stableCoin:
            assetsOnAccountByDollar.append([i["asset"], i["free"]])
        else:
            assetsOnAccountByDollar.append([i["asset"], get_conversion_value(i["asset"], stableCoin, i["free"])])
    

    fullAccountValue = 0    #Ez arész summa-za be mennyi stableCoin-t ér összsesen a fiók
    for i in assetsOnAccountByDollar:
        fullAccountValue += i[1]
    
    assetsOnAccountByPercentage = [] # Ez a rész váltja %-ra az account-on lévő cuccokat.
    for i in assetsOnAccountByDollar:
        assetsOnAccountByPercentage.append([i[0], (i[1]/fullAccountValue)*100])

    accountTargetAccountDifference = [] #Ez az elkövetkező pár sor rakja össze a listát amiben a százalék változások vannak benne.
    for i in orderList:
        talalt = False
        for j in assetsOnAccountByPercentage:
            if i[0] == j[0]:
                talalt = True
                accountTargetAccountDifference.append([i[0], i[1]-j[1]])
                break
        if not talalt:
            accountTargetAccountDifference.append([i[0], i[1]])

    for i in assetsOnAccountByPercentage:
        talalt = False
        for j in accountTargetAccountDifference:
            if i[0] == j[0]:
                talalt = True
        if not talalt and i[0] != stableCoin:
            accountTargetAccountDifference.append([i[0], -i[1]])

    accountTargetAccountDifference = [
        item for item in accountTargetAccountDifference 
        if abs(item[1]) >= rounding
    ]

    accountTargetAccountDifference = sorted(accountTargetAccountDifference, key=lambda x: x[1])

    for i in accountTargetAccountDifference:
        if i[1] < 0:
            #print([i[0]+stableCoin, round(get_conversion_value(stableCoin, i[0], abs((i[1]/100)*fullAccountValue)), 4)])
            margin_sell(i[0]+stableCoin, round_down(get_conversion_value(stableCoin, i[0], abs((i[1]/100)*fullAccountValue)), abs(int(math.log10(get_min_trade_amount(i[0]+stableCoin))))))
        else:
            #print([i[0]+stableCoin, round(get_conversion_value(stableCoin, i[0], abs((i[1]/100)*fullAccountValue)), 4)])
            margin_buy(i[0]+stableCoin, round_down(get_conversion_value(stableCoin, i[0], abs((i[1]/100)*fullAccountValue)), abs(int(math.log10(get_min_trade_amount(i[0]+stableCoin))))))


    return "\nSuccess\n"

#print(abs(int(math.log10(0.0001))))
#print(percentage_based_allocation([]))
margin_buy('SOLUSDC', 0.15)