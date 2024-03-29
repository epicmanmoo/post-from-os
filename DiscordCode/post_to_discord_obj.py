import datetime
import discord
from discord.embeds import EmptyEmbed
from enum import Enum
from fake_useragent import UserAgent
from operator import itemgetter
import requests
from requests.structures import CaseInsensitiveDict
import time
from tinydb import TinyDB, Query


class EventType(Enum):
    SALE = 'sale'
    LISTING = 'listing'
    SUCCESSFUL = 'successful'
    CREATED = 'created'


class _OpenSeaTransactionObject:
    discord_embed = None

    def __init__(self, name_, image_url_, seller_, buyer_, nft_price_, total_usd_cost_, link_, tx_type_,
                 image_thumbnail_url_, embed_icon_url_, rgb_color_, seller_link_, buyer_link_, num_of_assets_,
                 symbol_, rare_trait_list_, key_, db_):
        self.name = name_
        self.image_url = image_url_
        self.seller = seller_
        self.buyer = buyer_
        self.nft_price = nft_price_
        self.total_usd_cost = total_usd_cost_
        self.link = link_
        self.is_posted = False
        self.tx_type = tx_type_
        self.image_thumbnail_url = image_thumbnail_url_
        self.embed_icon_url = embed_icon_url_
        self.r = rgb_color_[0]
        self.g = rgb_color_[1]
        self.b = rgb_color_[2]
        self.seller_link = seller_link_
        self.buyer_link = buyer_link_
        self.num_of_assets = num_of_assets_
        self.symbol = symbol_
        self.rare_trait_list = rare_trait_list_
        self.key = key_
        self.db = db_

    def __eq__(self, other):
        return self.key == other.key
    
    def __hash__(self):
        return hash(('key', self.key))

    def create_discord_embed(self):
        icon_url = str(self.embed_icon_url) if self.embed_icon_url != 'None' else EmptyEmbed
        embed_color = discord.Color.from_rgb(self.r, self.g, self.b)
        embed = None
        title = self.name
        trait_desc = ''
        if self.rare_trait_list:
            for trait in self.rare_trait_list:
                trait_desc += str(trait[0]) + ': ' + str(trait[1]) + ' - ' + str(trait[2]) + '%' + '\n'
        if self.num_of_assets > 1:
            title = str(self.num_of_assets) + ' assets bought'
        if self.tx_type == EventType.SALE.value:
            embed = \
                discord.Embed(title=title, url=self.link,
                              description='{} {} (${})'.format(self.nft_price, self.symbol, self.total_usd_cost) +
                                          '\n' + ('\nRare Traits:' + '\n\n' + trait_desc if trait_desc != '' else '')
                              + '\nSeller: [{}]({})\nBuyer: [{}]({})'.format(self.seller, self.seller_link, self.buyer,
                                                                             self.buyer_link),
                              color=embed_color)
            embed.set_author(name='New Purchase!', icon_url=icon_url)
            if self.image_url is not None:
                embed.set_image(url=self.image_url)
        elif self.tx_type == EventType.LISTING.value:
            embed = \
                discord.Embed(title=self.name, url=self.link,
                              description='{} {} (${})'.format(self.nft_price, self.symbol, self.total_usd_cost) +
                                          '\n' + ('\nRare Traits:' + '\n\n' + trait_desc if trait_desc != '' else '') +
                              '\n Seller: [{}]({})'.format(self.seller, self.seller_link), color=embed_color)
            embed.set_author(name='New Listing!', icon_url=icon_url)
            embed.set_image(url=self.image_thumbnail_url)
        self.discord_embed = embed


class _PostFromOpenSeaDiscord:
    def __init__(self, values, needs_traits):
        self.needs_traits = needs_traits
        self.collection_name = values[0]
        self.contract_address = values[1]
        self.embed_icon_url = values[2]
        self.embed_rgb_color = values[3]
        self.os_api_key = values[4]
        self.os_events_url = 'https://api.opensea.io/api/v1/events'
        self.os_asset_url = 'https://api.opensea.io/api/v1/asset/'
        self.total_supply = -1
        self.response = None
        self.os_obj_to_post = None
        self.tx_type = None
        self.tx_db = TinyDB(self.collection_name + '_tx_hash_discord_db.json')
        self.tx_query = Query()
        self.id_db = TinyDB(self.collection_name + '_listing_id_discord_db.json')
        self.id_query = Query()
        self.tx_queue = []
        self.limit = 10
        self.ua = UserAgent()

    def get_recent_sales(self, tx_type):
        self.tx_type = tx_type
        if self.tx_type == EventType.SALE.value:
            event_type = EventType.SUCCESSFUL.value
        else:
            event_type = EventType.CREATED.value
        try:
            querystring = {
                'asset_contract_address': self.contract_address,
                'event_type': event_type,
                'only_opensea': 'false'
            }
            headers = CaseInsensitiveDict()
            headers['Accept'] = 'application/json'
            headers['User-Agent'] = self.ua.random
            headers['x-api-key'] = self.os_api_key
            self.response = requests.get(self.os_events_url, headers=headers, params=querystring, timeout=1.5)
            return self.response.status_code == 200
        except Exception as e:
            print(e, flush=True)
            return False

    def create_rare_trait_list(self, token_id):
        if self.total_supply == -1:
            test_coll_headers = CaseInsensitiveDict()
            test_coll_headers['User-Agent'] = self.ua.random
            test_coll_headers['x-api-key'] = self.os_api_key
            test_collection_name_url = 'https://api.opensea.io/api/v1/collection/{}'.format(self.collection_name)
            test_response = requests.get(test_collection_name_url, headers=test_coll_headers, timeout=3)
            if test_response.status_code == 200:
                collection_json = test_response.json()['collection']
                stats_json = collection_json['stats']
                self.total_supply = int(stats_json['total_supply'])
            else:
                return []
        try:
            rare_trait_list = []
            traits = None
            asset_url = self.os_asset_url + self.contract_address + '/' + token_id
            asset_headers = CaseInsensitiveDict()
            asset_headers['User-Agent'] = self.ua.random
            asset_headers['x-api-key'] = self.os_api_key
            asset_response = requests.get(asset_url, headers=asset_headers, timeout=3)
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

    def parse_response_objects(self):
        for i in range(0, self.limit):
            try:
                try:
                    base = self.response.json()['asset_events'][i]
                except IndexError:
                    continue
                if self.tx_type == EventType.SALE.value and base['asset_bundle'] is not None:
                    bundle = base['asset_bundle']
                    tx_hash = str(base['transaction']['transaction_hash'])
                    key = tx_hash
                    tx_exists = False if len(self.tx_db.search(self.tx_query.tx == key)) == 0 else True
                    if tx_exists:
                        continue
                    image_url = bundle['asset_contract']['image_url']
                    decimals = int(base['payment_token']['decimals'])
                    symbol = base['payment_token']['symbol']
                    nft_price = float('{0:.5f}'.format(int(base['total_price']) / (1 * 10 ** decimals)))
                    usd_price = float(base['payment_token']['usd_price'])
                    total_usd_cost = '{:.2f}'.format(round(nft_price * usd_price, 2))
                    link = bundle['permalink']
                    name = bundle['name']
                    num_of_assets = len(bundle['assets'])
                    seller_address = str(base['seller']['address'])
                    seller_link = 'https://opensea.io/{}'.format(seller_address)
                    buyer_address = str(base['winner_account']['address'])
                    buyer_link = 'https://opensea.io/{}'.format(buyer_address)
                    try:
                        seller = str(base['seller']['user']['username'])
                        if seller == 'None':
                            seller = seller_address[0:8]
                    except TypeError:
                        seller = seller_address[0:8]
                    try:
                        buyer = str(base['winner_account']['user']['username'])
                        if buyer == 'None':
                            buyer = buyer_address[0:8]
                    except TypeError:
                        buyer = buyer_address[0:8]
                    transaction = _OpenSeaTransactionObject(name, image_url, seller, buyer, nft_price,
                                                            total_usd_cost, link, self.tx_type, None,
                                                            self.embed_icon_url, self.embed_rgb_color, seller_link,
                                                            buyer_link, num_of_assets, symbol, None, key, self.tx_db)
                    transaction.create_discord_embed()
                    self.tx_queue.append(transaction)
                    continue
                asset = base['asset']
                name = str(asset['name'])
                image_url = asset['image_url']
                image_thumbnail_url = asset['image_thumbnail_url']
                seller_address = str(base['seller']['address'])
                seller_link = 'https://opensea.io/{}'.format(seller_address)
                buyer_address = str(base['winner_account']['address'])
                buyer_link = 'https://opensea.io/{}'.format(buyer_address)
                usd_price = float(base['payment_token']['usd_price'])
                link = asset['permalink']
            except TypeError:
                continue
            try:
                seller = str(base['seller']['user']['username'])
                if seller == 'None':
                    seller = seller_address[0:8]
            except TypeError:
                seller = seller_address[0:8]
            try:
                buyer = str(base['winner_account']['user']['username'])
                if buyer == 'None':
                    buyer = buyer_address[0:8]
            except TypeError:
                buyer = buyer_address[0:8]
            transaction = None
            token_id = asset['token_id']
            rare_trait_list = []
            if self.needs_traits:
                rare_trait_list = self.create_rare_trait_list(token_id)
            if self.tx_type == EventType.SALE.value:
                tx_hash = str(base['transaction']['transaction_hash'])
                key = tx_hash + ' ' + token_id
                tx_exists = False if len(self.tx_db.search(self.tx_query.tx == key)) == 0 else True
                if tx_exists:
                    continue
                try:
                    decimals = int(base['payment_token']['decimals'])
                    symbol = base['payment_token']['symbol']
                    nft_price = float('{0:.5f}'.format(int(base['total_price']) / (1 * 10 ** decimals)))
                    usd_price = float(base['payment_token']['usd_price'])
                    total_usd_cost = '{:.2f}'.format(round(nft_price * usd_price, 2))
                except (ValueError, TypeError):
                    continue
                transaction = _OpenSeaTransactionObject(name, image_url, seller, buyer, nft_price,
                                                        total_usd_cost, link, self.tx_type, image_thumbnail_url,
                                                        self.embed_icon_url, self.embed_rgb_color, seller_link,
                                                        buyer_link, 1, symbol, rare_trait_list, key, self.tx_db)
            elif self.tx_type == EventType.LISTING.value:
                try:
                    listing_id = str(base['id'])
                except TypeError:
                    continue
                key = listing_id + ' ' + token_id
                listing_exists = False if len(self.id_db.search(self.id_query.id == key)) == 0 else True
                if listing_exists:
                    continue
                try:
                    symbol = base['payment_token']['symbol']
                    price = float('{0:.5f}'.format(int(base['starting_price']) / 1e18))
                    total_usd_cost = '{:.2f}'.format(round(price * usd_price, 2))
                except (ValueError, TypeError):
                    continue
                transaction = _OpenSeaTransactionObject(name, image_url, seller, buyer, price, total_usd_cost, link,
                                                        self.tx_type, image_thumbnail_url, self.embed_icon_url,
                                                        self.embed_rgb_color, seller_link, buyer_link, 1, symbol,
                                                        rare_trait_list, key, self.id_db)
            transaction.create_discord_embed()
            self.tx_queue.append(transaction)
        return self.process_queue()

    def process_queue(self):
        if len(self.tx_db) > 200:
            for first in self.tx_db:
                self.tx_db.remove(doc_ids=[first.doc_id])
                break
        if len(self.id_db) > 200:
            for first in self.id_db:
                self.id_db.remove(doc_ids=[first.doc_id])
                break
        index = 0
        self.tx_queue = list(set(self.tx_queue))
        while index < len(self.tx_queue):
            cur_os_obj = self.tx_queue[index]
            sale_exists = False if len(self.tx_db.search(self.tx_query.tx == str(cur_os_obj.key))) == 0 else True
            listing_exists = False if len(self.id_db.search(self.id_query.id == str(cur_os_obj.key))) == 0 else True
            if cur_os_obj.is_posted or sale_exists or listing_exists:
                self.tx_queue.pop(index)
            else:
                index += 1
        if len(self.tx_queue) == 0:
            return False
        self.os_obj_to_post = self.tx_queue[-1]
        return True


class ManageFlowObj:
    def __init__(self, values, needs_traits):
        self.base_obj = _PostFromOpenSeaDiscord(values, needs_traits)
        self.tx_type = None
        self.date_time_now = None

    def check_os_api_status(self, tx_type):
        self.date_time_now = datetime.datetime.fromtimestamp(time.time()).strftime('%m/%d/%Y %H:%M:%S')
        self.tx_type = tx_type
        os_api_working = self.base_obj.get_recent_sales(self.tx_type)
        if not os_api_working:
            print('OS API is not working at roughly', self.date_time_now, flush=True)
            return False
        else:
            return True

    def check_if_new_post_exists(self):
        new_post_exists = self.base_obj.parse_response_objects()
        if not new_post_exists:
            print('No new post at roughly', self.date_time_now, flush=True)
            return False
        else:
            return True


async def try_to_post_embed_to_discord(mfo, channel):
    try:
        await channel.send(embed=mfo.base_obj.os_obj_to_post.discord_embed)
        if mfo.base_obj.os_obj_to_post.tx_type == EventType.SALE.value:
            mfo.base_obj.os_obj_to_post.db.insert({'tx': mfo.base_obj.os_obj_to_post.key})
        elif mfo.base_obj.os_obj_to_post.tx_type == EventType.LISTING.value:
            mfo.base_obj.os_obj_to_post.db.insert({'id': mfo.base_obj.os_obj_to_post.key})
        mfo.base_obj.os_obj_to_post.is_posted = True
        print('Posted to Discord at roughly', mfo.date_time_now, flush=True)
        return True
    except AttributeError:
        raise Exception('Channel does not exist OR I am not authorized to send messages in this channel.')
    except Exception as e:
        print(e, flush=True)
        print('Post to Discord error at roughly', mfo.date_time_now, flush=True)
        return False


async def eth_price(message):
    try:
        eth_price_url = 'https://min-api.cryptocompare.com/data/price?fsym=ETH&tsyms=USD'
        eth_price_request = requests.get(eth_price_url, timeout=1)
        if eth_price_request.status_code != 200:
            await message.channel.send('Sorry, API to fetch ETH price might be down right now.')
            return
        eth_price_usd = eth_price_request.json()['USD']
        await message.channel.send('${}'.format(eth_price_usd))
    except Exception as e:
        print(e, flush=True)
        return


async def gas_tracker(message, gas):
    try:
        fast_gas = gas[0]
        avg_gas = gas[1]
        slow_gas = gas[2]
        gas_embed = discord.Embed(title=':fuelpump: **Current Gas Prices**\n')
        gas_embed.description = ':zap: **Fast**\n{} Gwei\n\n:person_walking: **Average**\n{} Gwei\n\n:turtle: ' \
                                '**Slow**\n{} Gwei'.format(fast_gas, avg_gas, slow_gas)
        await message.channel.send(embed=gas_embed)
    except Exception as e:
        print(e, flush=True)
        await message.channel.send('Something went wrong. Please try again later.')
        return


async def custom_command_1(message, values, contract_address):
    name = values[contract_address][0]
    try:
        stats_url = 'https://api.opensea.io/api/v1/collection/{}/stats'.format(name)
        stats_request = requests.get(stats_url, timeout=1)
        if stats_request.status_code != 200:
            await message.channel.send('Sorry, Opensea API might be down right now.')
            return
        floor_price_eth = stats_request.json()['stats']['floor_price']
        eth_price_url = 'https://min-api.cryptocompare.com/data/price?fsym=ETH&tsyms=USD'
        eth_price_request = requests.get(eth_price_url, timeout=1)
        eth_price_usd = eth_price_request.json()['USD']
        floor_price_usd = round((floor_price_eth * eth_price_usd), 2)
        await message.channel.send('The floor for the collection is `Ξ{} (${})`. This might not be accurate, to see the'
                                   ' actual floor price, please visit the collection on Opensea: '
                                   '<https://opensea.io/collection/{}>'.format(floor_price_eth, floor_price_usd, name))
    except Exception as e:
        print(e, flush=True)
        await message.channel.send('Something went wrong. Please try again later.')
        return


async def custom_command_2(message, values, contract_address):
    ua = UserAgent()
    rgb = values[contract_address][3]
    os_api_key = values[contract_address][4]
    try:
        if len(message.content.split()) == 1:
            await message.channel.send('Please provide a valid Token ID.')
            return
        try:
            token_id = int(message.content.split()[1])
        except ValueError:
            return
        if token_id < 0:
            return
        asset_url = 'https://api.opensea.io/api/v1/assets?token_ids={}&asset_contract_address={}'\
            .format(token_id, contract_address)
        asset_headers = CaseInsensitiveDict()
        asset_headers['User-Agent'] = ua.random
        asset_headers['x-api-key'] = os_api_key
        asset_request = requests.get(asset_url, headers=asset_headers, timeout=1)
        if asset_request.status_code != 200:
            await message.channel.send('Sorry, Opensea API might be down right now.')
            return
        try:
            asset_base = asset_request.json()['assets'][0]
        except IndexError:
            await message.channel.send('Asset with Token ID = {} does not exist.'.format(token_id))
            return
        asset_name = asset_base['name']
        asset_img_url = asset_base['image_url']
        asset_link = asset_base['permalink']
        embed_color = discord.Color.from_rgb(rgb[0], rgb[1], rgb[2])
        asset_embed = discord.Embed(title='{}'.format(asset_name), url=asset_link, color=embed_color)
        if asset_img_url is not None:
            asset_embed.set_image(url=asset_img_url)
        else:
            asset_embed.description = 'Failed to fetch content metadata.\n\n'
        if asset_base['owner'] is not None:
            asset_owner = asset_base['owner']['address']
            asset_owner_link = 'https://opensea.io/{}'.format(asset_owner)
            asset_embed.description += 'Owner: [{}]({})'.format(asset_owner[0:8], asset_owner_link)
        await message.channel.send(embed=asset_embed)
    except Exception as e:
        print(e, flush=True)
        await message.channel.send('Something went wrong. Please try again later.')
        return
