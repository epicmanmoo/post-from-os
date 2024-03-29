import sys
sys.path.append('../')
import datetime  # noqa: E402
from fake_useragent import UserAgent  # noqa: E402
from HelperCode.tweet import Tweet  # noqa: E402
from operator import itemgetter  # noqa: E402
import requests  # noqa: E402
from requests.structures import CaseInsensitiveDict  # noqa: E402
import time  # noqa: E402
from tinydb import TinyDB, Query  # noqa: E402


class _OpenSeaTransactionObject:
    def __init__(self, name_, image_url_, nft_price_, total_usd_cost_, link_, rare_trait_list_,
                 twitter_tags_, num_of_assets_, key_, tx_hash_, symbol_):
        self.twitter_caption = None
        self.name = name_
        self.image_url = image_url_
        self.nft_price = nft_price_
        self.total_usd_cost = total_usd_cost_
        self.link = link_
        self.is_posted = False
        self.rare_trait_list = rare_trait_list_
        self.twitter_tags = twitter_tags_
        self.num_of_assets = num_of_assets_
        self.key = key_
        self.tx_hash = tx_hash_
        self.symbol = symbol_

    def __eq__(self, other):
        return self.key == other.key

    def __hash__(self):
        return hash(('key', self.key))

    def create_twitter_caption(self):
        self.twitter_caption = '{} bought for {} {} (${})\n'.format(self.name, self.nft_price, self.symbol,
                                                                    self.total_usd_cost)
        if self.num_of_assets > 1:
            self.twitter_caption = '{}\n{} assets bought for {} {} (${})\n'.\
                format(self.name, self.num_of_assets, self.nft_price, self.symbol, self.total_usd_cost)
        stringed_twitter_tags = " ".join(self.twitter_tags)
        remaining_characters = 280 - len(self.twitter_caption) - len(self.link) - len(stringed_twitter_tags)
        if self.rare_trait_list:
            if remaining_characters >= 13 and len(self.rare_trait_list) != 0:
                self.twitter_caption += 'Rare Traits:\n'
                full_rare_trait_sentence = ''
                for rare_trait in self.rare_trait_list:
                    next_rare_trait_sentence = '{}: {} - {}%\n'.format(rare_trait[0], rare_trait[1], str(rare_trait[2]))
                    if len(next_rare_trait_sentence) + len(full_rare_trait_sentence) > remaining_characters:
                        break
                    full_rare_trait_sentence += next_rare_trait_sentence
                self.twitter_caption += full_rare_trait_sentence
        self.twitter_caption += '\n\n' + self.link + '\n\n' + \
                                (stringed_twitter_tags if stringed_twitter_tags != 'None' else '')


class _PostFromOpenSeaTwitter:
    def __init__(self, values):
        self.twitter_tags = values[0]
        self.collection_name = values[1]
        self.collection_stats = values[2]
        self.twitter_keys = values[3]
        self.os_api_key = values[4]
        self.ether_scan_api_key = values[5]
        self.collection_name_for_ether_scan = values[6]
        self.collection_needs_traits = values[7]
        self.args = values[7]
        self.image_db = None
        if type(self.args) is list:
            self.collection_needs_traits = self.args[0]
            self.image_db = TinyDB(self.args[1])
            self.image_query = Query()
        self.file_name = self.collection_name + '_twitter_asynchronous.jpeg'
        self.total_supply = self.collection_stats[0]
        self.contract_address = self.collection_stats[1]
        self.os_events_url = 'https://api.opensea.io/api/v1/events/'
        self.os_asset_url = 'https://api.opensea.io/api/v1/asset/'
        self.ether_scan_api_url = 'https://api.etherscan.io/api'
        self.response = None
        self.os_obj_to_post = None
        self.tx_db = TinyDB(self.collection_name + '_tx_hash_twitter_db_asynchronous.json')
        self.tx_query = Query()
        self.tx_queue = []
        self.os_limit = 10
        self.ether_scan_limit = int(self.os_limit * 1.5)
        self.tweet = Tweet(
            self.twitter_keys[0],
            self.twitter_keys[1],
            self.twitter_keys[2],
            self.twitter_keys[3]
        )
        self.ua = UserAgent()

    def __del__(self):
        self.tweet.close()

    def get_recent_sales(self):  # gets {limit} most recent sales
        if self.os_api_key == 'None':
            return False
        try:
            query_strings = {
                'asset_contract_address': self.contract_address,
                'event_type': 'successful',
                'only_opensea': 'false'
            }
            headers = CaseInsensitiveDict()
            headers['Accept'] = 'application/json'
            headers['User-Agent'] = self.ua.random
            headers['x-api-key'] = self.os_api_key
            self.response = requests.get(self.os_events_url, headers=headers, params=query_strings, timeout=1)
            return self.response.status_code == 200
        except Exception as e:
            print(e, flush=True)
            return False

    def parse_response_objects(self):
        for i in range(0, self.os_limit):
            try:
                try:
                    base = self.response.json()['asset_events'][i]
                except IndexError:
                    continue
                tx_hash = str(base['transaction']['transaction_hash'])
                key = tx_hash
                if base['asset_bundle'] is not None:
                    tx_exists = False if len(self.tx_db.search(self.tx_query.tx == key)) == 0 else True
                    if tx_exists:
                        continue
                    bundle = base['asset_bundle']
                    image_url = bundle['asset_contract']['image_url']
                    decimals = int(base['payment_token']['decimals'])
                    symbol = base['payment_token']['symbol']
                    nft_price = float('{0:.5f}'.format(int(base['total_price']) / (1 * 10 ** decimals)))
                    usd_price = float(base['payment_token']['usd_price'])
                    total_usd_cost = '{:.2f}'.format(round(nft_price * usd_price, 2))
                    link = bundle['permalink']
                    name = bundle['name']
                    num_of_assets = len(bundle['assets'])
                    transaction = _OpenSeaTransactionObject(name, image_url, nft_price, total_usd_cost, link, [],
                                                            self.twitter_tags, num_of_assets, key, tx_hash, symbol)
                    transaction.create_twitter_caption()
                    self.tx_queue.append(transaction)
                    continue
                asset = base['asset']
                name = str(asset['name'])
                image_url = asset['image_url']
            except TypeError:
                continue
            try:
                token_id = asset['token_id']
                key = tx_hash + ' ' + token_id
                tx_exists = False if len(self.tx_db.search(self.tx_query.tx == key)) == 0 else True
                if tx_exists:
                    continue
                # fetch_coin
                decimals = int(base['payment_token']['decimals'])
                symbol = base['payment_token']['symbol']
                nft_price = float('{0:.5f}'.format(int(base['total_price']) / (1 * 10 ** decimals)))
                usd_price = float(base['payment_token']['usd_price'])
                total_usd_cost = '{:.2f}'.format(round(nft_price * usd_price, 2))
                link = asset['permalink']
            except (ValueError, TypeError):
                continue
            rare_trait_list = []
            if self.collection_needs_traits:
                rare_trait_list = self.create_rare_trait_list(token_id)
            transaction = _OpenSeaTransactionObject(name, image_url, nft_price, total_usd_cost, link,
                                                    rare_trait_list, self.twitter_tags, 1, key, tx_hash, symbol)
            transaction.create_twitter_caption()
            self.tx_queue.append(transaction)
        return self.process_queue()

    def process_queue(self):
        if len(self.tx_db) > 200:
            for first in self.tx_db:
                self.tx_db.remove(doc_ids=[first.doc_id])
                break
        index = 0
        self.tx_queue = list(set(self.tx_queue))
        while index < len(self.tx_queue):
            cur_os_obj = self.tx_queue[index]
            tx_exists = False if len(self.tx_db.search(self.tx_query.tx == str(cur_os_obj.key))) == 0 else True
            if cur_os_obj.is_posted or tx_exists:
                self.tx_queue.pop(index)
            else:
                index += 1
        if len(self.tx_queue) == 0:
            return False
        self.os_obj_to_post = self.tx_queue[-1]
        return True

    def download_image(self):
        if self.os_obj_to_post.image_url is None:
            return True
        img = open(self.file_name, 'wb')
        try:
            img_response = requests.get(self.os_obj_to_post.image_url, stream=True, timeout=3)
            img.write(img_response.content)
            img.close()
            return True
        except Exception as e:
            img.close()
            print(e, flush=True)
            return False

    def create_rare_trait_list(self, token_id):
        try:
            rare_trait_list = []
            traits = None
            asset_url = self.os_asset_url + self.contract_address + '/' + token_id
            asset_headers = CaseInsensitiveDict()
            asset_headers['User-Agent'] = self.ua.random
            asset_headers['x-api-key'] = self.os_api_key
            asset_response = requests.get(asset_url, headers=asset_headers, timeout=1.5)
            if asset_response.status_code == 200:
                traits = asset_response.json()['traits']
            if traits is None:
                return
            for trait in traits:
                trait_type = trait['trait_type']
                trait_value = trait['value']
                trait_count = trait['trait_count']
                rarity_decimal = float(trait_count / self.total_supply)
                if rarity_decimal <= 0.05:
                    rare_trait_list.append([trait_type, trait_value, round(rarity_decimal * 100, 2)])
            rare_trait_list.sort(key=itemgetter(2))
            return rare_trait_list
        except Exception as e:
            print(e, flush=True)
            return

    def process_via_ether_scan(self):
        try:
            tx_transfer_params = {
                'module': 'account',
                'action': 'tokennfttx',
                'contractaddress': self.contract_address,
                'startblock': 0,
                'endblock': 999999999,
                'sort': 'desc',
                'apikey': self.ether_scan_api_key,
                'page': 1,
                'offset': self.ether_scan_limit
            }
            get_tx_transfer_request = requests.get(self.ether_scan_api_url, params=tx_transfer_params, timeout=1.5)
            tx_response = get_tx_transfer_request.json()
            for i in range(0, self.ether_scan_limit):
                tx_response_base = tx_response['result'][i]
                token_id = tx_response_base['tokenID']
                tx_hash = str(tx_response_base['hash'])
                tx_exists = False if len(self.tx_db.search(self.tx_query.tx == tx_hash)) == 0 else True
                if tx_exists:
                    continue
                key = tx_hash + ' ' + token_id
                tx_exists = False if len(self.tx_db.search(self.tx_query.tx == key)) == 0 else True
                if tx_exists:
                    continue
                if i + 1 != self.ether_scan_limit:  # check if next tx has is same as this one's
                    next_tx_hash = str(tx_response['result'][i + 1]['hash'])
                    next_key = next_tx_hash + ' ' + token_id
                    if key == next_key:
                        continue
                else:  # if we are at the end of the list: fetch the api again, increase offset by 1, and check if same
                    tx_transfer_params['offset'] += 1
                    get_new_tx_transfer_request = requests.get(self.ether_scan_api_url, params=tx_transfer_params,
                                                               timeout=1.5)
                    new_tx_response = get_new_tx_transfer_request.json()
                    next_tx_transfer_hash = str(new_tx_response['result'][i + 1]['hash'])
                    next_key = next_tx_transfer_hash + ' ' + token_id
                    if key == next_key:
                        continue
                from_address = tx_response_base['from']
                if from_address == '0x0000000000000000000000000000000000000000':
                    continue
                tx_hash_params = {
                    'module': 'proxy',
                    'action': 'eth_getTransactionByHash',
                    'txhash': tx_hash,
                    'apikey': self.ether_scan_api_key
                }
                get_tx_hash_request = requests.get(self.ether_scan_api_url, params=tx_hash_params, timeout=1.5)
                tx_details_response_base = get_tx_hash_request.json()['result']
                tx_hex_value = tx_details_response_base['value']
                tx_value = float(int(tx_hex_value, 16) / 1e18)
                eth_price_params = {
                    'module': 'stats',
                    'action': 'ethprice',
                    'apikey': self.ether_scan_api_key
                }
                eth_price_req = requests.get(self.ether_scan_api_url, params=eth_price_params, timeout=1.5)
                eth_price_base = eth_price_req.json()['result']
                eth_usd_price = eth_price_base['ethusd']
                usd_nft_cost = round(float(eth_usd_price) * tx_value, 2)
                input_type = tx_details_response_base['input']
                symbol = 'ETH'
                if input_type.startswith('0xab834bab'):  # atomic match
                    if tx_value == 0.0:
                        tx_hash_params = {
                            'module': 'proxy',
                            'action': 'eth_getTransactionReceipt',
                            'txhash': tx_hash,
                            'apikey': self.ether_scan_api_key
                        }
                        get_tx_receipt_request = requests.get(self.ether_scan_api_url, params=tx_hash_params,
                                                              timeout=1.5)
                        first_log = get_tx_receipt_request.json()['result']['logs'][0]
                        data = first_log['data']
                        if data != '0x':
                            address = first_log['address']
                            # fetch_coin
                            if address == '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2':  # WETH is common, no API needed
                                symbol = 'WETH'
                                tx_value = float(int(data, 16) / 1e18)
                                usd_nft_cost = round(float(eth_usd_price) * tx_value, 2)
                            else:
                                token_info_req = requests.get(
                                    'https://api.ethplorer.io/getTokenInfo/{}?apiKey=freekey'.format(address),
                                    timeout=3)
                                token_info_json = token_info_req.json()
                                symbol = token_info_json['symbol']
                                decimals = int(token_info_json['decimals'])
                                price = round(token_info_json['price']['rate'], 3)
                                tx_value = float(int(data, 16) / (1 * 10 ** decimals))
                                usd_nft_cost = round(float(price) * tx_value, 2)
                    name = '{} #{}'.format(self.collection_name_for_ether_scan, token_id)
                    asset_link = 'https://opensea.io/assets/{}/{}'.format(self.contract_address, token_id)
                    rare_trait_list = []
                    if self.collection_needs_traits:
                        rare_trait_list = self.create_rare_trait_list(token_id)
                    image_url = None
                    if self.image_db is not None:
                        asset_from_db = self.image_db.search(self.image_query.id == int(token_id))
                        image_url = asset_from_db[0]['image_url']
                    transaction = _OpenSeaTransactionObject(name, image_url, tx_value, usd_nft_cost, asset_link,
                                                            rare_trait_list, self.twitter_tags, 1, key, tx_hash, symbol)
                    transaction.create_twitter_caption()
                    self.tx_queue.append(transaction)
            return self.process_queue()
        except Exception as e:
            print(e, flush=True)
            return -1

    def post_to_twitter(self):
        if self.os_obj_to_post.image_url is None:
            res = self.tweet.post(self.os_obj_to_post.twitter_caption)
            if res == -1:
                return False
            self.tx_db.insert({'tx': self.os_obj_to_post.key})
            self.tx_db.insert({'tx': self.os_obj_to_post.tx_hash})
            self.os_obj_to_post.is_posted = True
            return True

        res = self.tweet.post(self.os_obj_to_post.twitter_caption, self.file_name)
        if res == -1:
            return False
        self.os_obj_to_post.is_posted = True
        self.tx_db.insert({'tx': self.os_obj_to_post.key})
        self.tx_db.insert({'tx': self.os_obj_to_post.tx_hash})
        return True


class ManageFlowObj:
    def __init__(self, values):
        self.__base_obj = _PostFromOpenSeaTwitter(values)
        self.date_time_now = None

    def check_os_api_status(self):
        self.date_time_now = datetime.datetime.fromtimestamp(time.time()).strftime('%m/%d/%Y %H:%M:%S')
        os_api_working = self.__base_obj.get_recent_sales()
        if not os_api_working:
            print('OS API is not working at roughly', self.date_time_now, flush=True)
            return False
        else:
            return True

    def check_ether_scan_api_status(self):
        print('Attempting to use Ether Scan API at roughly', self.date_time_now, flush=True)
        new_post_exists = self.__base_obj.process_via_ether_scan()
        if new_post_exists == -1:
            print('Error processing via Ether Scan API at roughly', self.date_time_now, flush=True)
            return -1
        elif new_post_exists:
            return True
        else:
            print('No new post at roughly', self.date_time_now, flush=True)
            return False

    def check_if_new_post_exists(self):
        new_post_exists = self.__base_obj.parse_response_objects()
        if not new_post_exists:
            print('No new post at roughly', self.date_time_now, flush=True)
            return False
        else:
            return True

    def try_to_download_image(self):
        image_downloaded = self.__base_obj.download_image()
        if not image_downloaded:
            print('Downloading image error at roughly', self.date_time_now, flush=True)
            return False
        else:
            return True

    def try_to_post_to_twitter(self):
        posted_to_twitter = self.__base_obj.post_to_twitter()
        if posted_to_twitter:
            print('Posted to Twitter at roughly', self.date_time_now, flush=True)
            return True
        else:
            print('Post to Twitter error at roughly', self.date_time_now, flush=True)
            return False
