using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Net.Http;
using System.Threading.Tasks;
using Newtonsoft.Json;//Ezt fel kell rakni a project-be. Ehhez "Solution 'TheAlgorithm'..."-ra kell nyomni (Jobb klikk), majd "Manage NuGet packeages for solution..." és ott a "Newtonsoft.Json" fog kelleni
using Microsoft.Extensions.Configuration;//Same shit, csak itt a "Microsoft.Extensions.Configuration" fog kelleni


namespace TheAlgorithm
{

    public class BinanceApi
    {
        private readonly string apiKey;
        private readonly string apiSecret;
        private readonly string baseUrl = "https://api.binance.com";
        private readonly HttpClient httpClient;

        //public BinanceApi(IConfiguration config)//Constructor
        public BinanceApi()//Constructor
        {
            //apiKey = config["Binance:ApiKey"];
            //apiSecret = config["Binance:ApiSecret"];
            apiKey = //Your API KEY
            apiSecret = //Your API Secret
            httpClient = new HttpClient();
            httpClient.DefaultRequestHeaders.Add("X-MBX-APIKEY", apiKey);
        }

        public async Task<List<MarginAsset>> GetMarginAccount()
        {
            long timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
            string queryString = $"timestamp={timestamp}";
            string signature = SignRequest(queryString);

            string url = $"{baseUrl}/sapi/v1/margin/account?{queryString}&signature={signature}";
            var response = await httpClient.GetAsync(url);

            if (response.IsSuccessStatusCode)
            {
                var json = await response.Content.ReadAsStringAsync();
                var data = JsonConvert.DeserializeObject<MarginAccountResponse>(json);

                return data.UserAssets
                    .Where(a => Convert.ToDouble(a.Free) > 0 || Convert.ToDouble(a.Borrowed) > 0)
                    .Select(a => new MarginAsset
                    {
                        Asset = a.Asset,
                        Free = Convert.ToDouble(a.Free),
                        Borrowed = Convert.ToDouble(a.Borrowed)
                    })
                    .ToList();
            }
            Console.WriteLine($"Error: {response.StatusCode} {await response.Content.ReadAsStringAsync()}");
            return null;
        }

        public async Task<double?> GetMinTradeAmount(string symbol)//Olyan bemenet kell neki mint "SOLUSDC". Megmondja mennyi a minimum amit vehetsz belőle
        {
            string url = $"{baseUrl}/api/v3/exchangeInfo";
            var response = await httpClient.GetAsync(url);

            if (response.IsSuccessStatusCode)
            {
                var json = await response.Content.ReadAsStringAsync();
                var data = JsonConvert.DeserializeObject<ExchangeInfoResponse>(json);

                var symbolInfo = data.Symbols.FirstOrDefault(s => s.Symbol == symbol);
                if (symbolInfo != null)
                {
                    var lotSizeFilter = symbolInfo.Filters
                        .FirstOrDefault(f => f.FilterType == "LOT_SIZE");
                    if (lotSizeFilter != null)
                        return Convert.ToDouble(lotSizeFilter.MinQty);
                }
            }
            Console.WriteLine($"Symbol not found or error. Status: {response.StatusCode}");
            return null;
        }

        public static double RoundUpToFraction(double number, double fraction) => Math.Ceiling(number / fraction) * fraction;//Segít számolni az auto eladós/vásárlós részét a többi function-nek

        public static double RoundDownToFraction(double number, double fraction) => Math.Floor(number / fraction) * fraction;//Segít számolni az auto eladós/vásárlós részét a többi function-nek

        public async Task<(double free, double borrowed)> GetCoinBalance(string coinLabel)//Megmondja mennyi van egy adott function-ből.
        {
            var assets = await GetMarginAccount();
            if (assets != null)
            {
                var asset = assets.FirstOrDefault(a => a.Asset == coinLabel);
                if (asset != null)
                    return (asset.Free, asset.Borrowed);
            }
            return (0.0, 0.0);
        }

        private string SignRequest(string queryString)//Alap segítő function
        {
            using (var hmac = new HMACSHA256(Encoding.UTF8.GetBytes(apiSecret)))
            {
                byte[] hash = hmac.ComputeHash(Encoding.UTF8.GetBytes(queryString));
                return BitConverter.ToString(hash).Replace("-", "").ToLower();
            }
        }

        public async Task PlaceMarginTrade(string symbol, string side, double quantity)//Symbol mint "SOLUSDC", ide kell a Stable coin is
        {
            var parameters = new Dictionary<string, string>
            {
                { "symbol", symbol },
                { "side", side },
                { "type", "MARKET" },
                { "quantity", quantity.ToString() },
                { "isIsolated", "FALSE" },
                { "timestamp", DateTimeOffset.UtcNow.ToUnixTimeMilliseconds().ToString() }
            };

            await ExecuteTrade(parameters);
        }

        public async Task PlaceCustomMarginTrade(string symbol, string side, string type, double quantity, bool isIsolated = false)//Pont olyan mint a felette lévő, de több mindent írhatsz át. Nem tudom miért használnád.
        {
            var parameters = new Dictionary<string, string>
            {
                { "symbol", symbol },
                { "side", side },
                { "type", type },
                { "quantity", quantity.ToString() },
                { "isIsolated", isIsolated.ToString().ToUpper() },
                { "timestamp", DateTimeOffset.UtcNow.ToUnixTimeMilliseconds().ToString() }
            };

            await ExecuteTrade(parameters);
        }

        public async Task MarginSell(string symbol, double quantity) => await PlaceMarginTrade(symbol, "SELL", quantity);//Symbol mint "SOLUSDC", ide kell a Stable coin is

        public async Task MarginBuy(string symbol, double quantity) => await PlaceMarginTrade(symbol, "BUY", quantity);//Symbol mint "SOLUSDC", ide kell a Stable coin is

        public async Task OpenShort(string symbol, double quantity)//Olyan symbol-t szeretne, mint "SOL", NEM "SOLUSDC"
        {
            var parameters = new Dictionary<string, string>
            {
                { "asset", symbol },
                { "amount", quantity.ToString() },
                { "timestamp", DateTimeOffset.UtcNow.ToUnixTimeMilliseconds().ToString() }
            };

            // ABC-be rendezi a paraméterket mert az kell
            var orderedParams = parameters.OrderBy(p => p.Key).ToList();
            string queryString = string.Join("&", orderedParams.Select(p => $"{p.Key}={p.Value}"));
            string signature = SignRequest(queryString);

            // Minden paramétert belerak az URL-be (nem csak a signature-t)
            string fullUrl = $"{baseUrl}/sapi/v1/margin/loan?{queryString}&signature={signature}";
            var response = await httpClient.PostAsync(fullUrl, null);
            Console.WriteLine($"Borrow Response: {await response.Content.ReadAsStringAsync()}");//Ha ezt üresen kapod vissza akkor siker (Azaz az üzenet része siker).      Bár ez csak debug, tehát nincs effektje a kódon
        }

        public async Task CloseShort(string symbol, double quantity, string stablecoin = "USDC")//Olyan symbol-t szeretne, mint "SOL", NEM "SOLUSDC"
        {
            var (free, borrowed) = await GetCoinBalance(symbol);                        //<--------- Megnézu mennyi van az adott coin-ból
            var minTrade = await GetMinTradeAmount($"{symbol}{stablecoin}");

            if (minTrade.HasValue && free < borrowed)                                   //<---------- Ha nincs elég a visszafizetéshez, akkor kiszámolja mennyit kell venni és vesz annyit
            {
                double difference = RoundUpToFraction(borrowed - free, minTrade.Value);
                await PlaceMarginTrade($"{symbol}{stablecoin}", "BUY", Math.Max(difference, minTrade.Value));
            }

            var parameters = new Dictionary<string, string>                 //<---------------- Itt kezdődik a visszafizetés. Ezek sorba raknak meg minden.
            {
                { "asset", symbol },
                { "amount", quantity.ToString() },
                { "timestamp", DateTimeOffset.UtcNow.ToUnixTimeMilliseconds().ToString() }
            };

            // 1. Sort parameters alphabetically
            var orderedParams = parameters.OrderBy(p => p.Key).ToList();
            string queryString = string.Join("&", orderedParams.Select(p => $"{p.Key}={p.Value}"));

            // 2. Generate signature
            string signature = SignRequest(queryString);

            // 3. Create form content
            var formContent = new FormUrlEncodedContent(orderedParams.Concat(new[]
            {
                new KeyValuePair<string, string>("signature", signature)
            }));

            // 4. Send as POST with form data
            var response = await httpClient.PostAsync($"{baseUrl}/sapi/v1/margin/repay", formContent);
            Console.WriteLine($"Repay Response: {await response.Content.ReadAsStringAsync()}");//Ha ezt üresen kapod vissza akkor siker (Azaz az üzenet része siker).      Bár ez csak debug, tehát nincs effektje a kódon

            (free, borrowed) = await GetCoinBalance(symbol); //<--------------- Ha van bármennyi extra (eladható mennyiségű) coin, azt eladja
            if (minTrade.HasValue && free > 0)
            {
                double bonus = RoundDownToFraction(free, minTrade.Value);
                if (bonus > 0)
                    await PlaceMarginTrade($"{symbol}{stablecoin}", "SELL", bonus);
            }
        }

        public async Task DumbCloseShort(string symbol, double quantity) //Ezt valszeg nehasználd, a másik Máté kérésére sokkal jobbra lett csinálva. De ez ugyan az az extra varázslat nélkül (az elején és végén).
        {
            var parameters = new Dictionary<string, string>
            {
                { "asset", symbol },
                { "amount", quantity.ToString() },
                { "timestamp", DateTimeOffset.UtcNow.ToUnixTimeMilliseconds().ToString() }
            };

            // Same as above
            var orderedParams = parameters.OrderBy(p => p.Key).ToList();
            string queryString = string.Join("&", orderedParams.Select(p => $"{p.Key}={p.Value}"));
            string signature = SignRequest(queryString);

            var formContent = new FormUrlEncodedContent(orderedParams.Concat(new[]
            {
                new KeyValuePair<string, string>("signature", signature)
            }));

            var response = await httpClient.PostAsync($"{baseUrl}/sapi/v1/margin/repay", formContent);
            Console.WriteLine($"Repay Response: {await response.Content.ReadAsStringAsync()}");//Ha ezt üresen kapod vissza akkor siker (Azaz az üzenet része siker).      Bár ez csak debug, tehát nincs effektje a kódon
        }

        public async Task<double?> GetCoinQuantityForUsd(string coinLabel, double usdValue, string stableCoin = "USDC")//Add meg a coin label-t mint "SOL", és visszaadja, hogy X USD mennyire lenne elég.
        {
            string symbol = $"{coinLabel}{stableCoin}";
            var response = await httpClient.GetAsync($"{baseUrl}/api/v3/ticker/price?symbol={symbol}");

            if (response.IsSuccessStatusCode)
            {
                var json = await response.Content.ReadAsStringAsync();
                var data = JsonConvert.DeserializeObject<PriceResponse>(json);
                double coinPrice = Convert.ToDouble(data.Price);
                // Console.WriteLine($"Current price of {coinLabel}: {coinPrice} {stableCoin}");
                return usdValue / coinPrice;
            }

            Console.WriteLine($"Error fetching price for {coinLabel}: {response.StatusCode}");
            return null;
        }

        private async Task ExecuteTrade(Dictionary<string, string> parameters)//Erre visszajön a Margin-os function. Azaz 
        {
            /*string queryString = SignRequest(string.Join("&", parameters.Select(p => $"{p.Key}={p.Value}")));
            var response = await httpClient.PostAsync($"{baseUrl}/sapi/v1/margin/order?{queryString}", null);
            Console.WriteLine($"Trade Response: {await response.Content.ReadAsStringAsync()}");*/

            // Sort parameters alphabetically by key
            var orderedParams = parameters.OrderBy(p => p.Key).ToList();

            // Create query string from SORTED parameters
            string unsignedQuery = string.Join("&", orderedParams.Select(p => $"{p.Key}={p.Value}"));

            // Generate signature
            string signature = SignRequest(unsignedQuery);

            // Construct URL
            string url = $"{baseUrl}/sapi/v1/margin/order?{unsignedQuery}&signature={signature}";

            Console.WriteLine($"Request URL: {url}");
            var response = await httpClient.PostAsync(url, null);
            Console.WriteLine($"Trade Response: {await response.Content.ReadAsStringAsync()}");
        }
    }

    // Supporting classes for JSON deserialization
    public class MarginAsset
    {
        public string Asset { get; set; }
        public double Free { get; set; }
        public double Borrowed { get; set; }
    }

    public class MarginAccountResponse
    {
        [JsonProperty("userAssets")]
        public List<MarginAssetResponse> UserAssets { get; set; }
    }

    public class MarginAssetResponse
    {
        [JsonProperty("asset")]
        public string Asset { get; set; }
        [JsonProperty("free")]
        public string Free { get; set; }
        [JsonProperty("borrowed")]
        public string Borrowed { get; set; }
    }

    public class ExchangeInfoResponse
    {
        [JsonProperty("symbols")]
        public List<SymbolInfo> Symbols { get; set; }
    }

    public class SymbolInfo
    {
        [JsonProperty("symbol")]
        public string Symbol { get; set; }
        [JsonProperty("filters")]
        public List<FilterInfo> Filters { get; set; }
    }

    public class FilterInfo
    {
        [JsonProperty("filterType")]
        public string FilterType { get; set; }
        [JsonProperty("minQty")]
        public string MinQty { get; set; }
    }

    public class PriceResponse
    {
        [JsonProperty("price")]
        public string Price { get; set; }
    }
}
