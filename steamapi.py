import urllib, urllib2
import json
import socket

apikey = 'YOUR STEAM API KEY HERE'
getinvurl = 'http://api.steampowered.com/IEconItems_440/GetPlayerItems/v0001/?'
get64biturl = 'http://api.steampowered.com/ISteamUser/ResolveVanityURL/v0001/?'
getschemaurl = 'http://api.steampowered.com/IEconItems_440/GetSchema/v0001/?'
basevals = {'key':apikey, 'language':'en_US', 'format': 'json'}
INVERRORS = {8:'Steamid parameter missing or invalid.', 15:'Backpack is private.', 18:'Given steamid does not exist.'}
SCHEMAFILE = 'schema.json'

class SteamAPIError(Exception):
    pass

class SteamAPITimeout(SteamAPIError):
    pass

def geturl(url, **vals):
    try:
        u = urllib2.urlopen(url + urllib.urlencode(vals), timeout=10)
        page = json.load(u)
        u.close()
        return page
    except socket.timeout:
        return None
    except urllib2.URLError, e:
        if hasattr(e, 'reason') and isinstance(e.reason, socket.timeout):
            return None
        else:
            raise

def resolve_vanity(playerid):
    page = geturl(get64biturl, vanityurl=playerid, **basevals)
    if page == None:
        raise SteamAPITimeout()
    response = page['response']
    success = response['success']
    if success == 42:
        message = response['message']
        if not message:
            message = "Couldn't resolve vanity url"
        raise SteamAPIError(message)
    return response['steamid']

class Item(dict):
    def __init__(self, schema, item):
        dict.__init__(self)
        i = schema.items[item['defindex']]
        self.update(i)
        self.update(item)
        self['name'] = self['item_name']
        if 'custom_name' in self:
            self['name'] = '"' + self['custom_name'] + '"'
        self['slot'] = self.get('item_slot', '')
        self.pop('item_slot', None)
        self['classes'] = self.get('used_by_classes', [])
        self.pop('used_by_classes', None)
        self['qualityName'] = schema.qualities[self['quality']]
        self['originName'] = schema.origins[self['origin']]
        self['inventory'] &= ((1<<16) - 1)
        self['tradable'] = not self.get('flag_cannot_trade', False)
        self.pop('flag_cannot_trade', None)
        self['craftable'] = not self.get('flag_cannot_craft', False)
        self.pop('flag_cannot_craft', None)

    #apparently there's a problem with the repr() function, and there's no way
    #around it. So when you try to just get the representation of a Detective
    #Noir, it will throw a unicode error because it's got a character from
    #extended ASCII. You'll have to call this directly with i.__repr__()
    def __repr__(self):
        try:
            ret = "<Item : Level {level} {qualityName} {name}>".format(**self)
        except UnicodeEncodeError:
            ret = u"<Item : Level {level} {qualityName} {name}>".format(**self)
        return ret

    def usable_by_class(cls):
        return not self['classes'] or cls in self['classes']

#upgrading implementation to use proper HTTP headers and cache it client-side
class Schema(object):
    def __init__(self):
        self.qualities = []
        self.origins = []
        self.items = {}
        self.attributes = {}
        self.update()

    def search(self, name):
        retval = []
        for item in self.items.values():
            if name.lower() in item['item_name'].lower():
                retval.append(item)
        return retval

    def update(self):
        #read file first
        file_exists = False
        page_exists = False
        try:
            f = open(SCHEMAFILE, 'r')
            page = json.load(f)
            f.close()
            file_exists = True
        except IOError, e:
            #error opening the file, so, yeah.
            pass
        request = urllib2.Request(getschemaurl + urllib.urlencode(basevals))
        if file_exists:
            request.add_header("If-Modified-Since", page['last-modified'])
        try:
            u = urllib2.urlopen(request)
            page = json.load(u)
            page['last-modified'] = u.headers.getheader('last-modified')
            u.close()
            page_exists = True
        except urllib2.HTTPError, e:
            #304 is "Not Modified" error
            if e.code == 304:
                #read from file instead
                pass
            else:
                #try to read from file anyway?
                #maybe mention this
                #logger.warning
                pass
        except urllib2.URLError, e:
            if hasattr(e, 'reason') and isinstance(e.reason, socket.timeout):
                #logger.warning
                pass
        except socket.timeout:
            #logger.warning
            pass
        if not file_exists and not page_exists:
            raise SteamAPIError("Fukken all kinds of fukked up. aint no cache, aint no shit, aint no nuttin")
        result = page['result']
        if result['status'] != 1:
            raise SteamAPIError("Schema status other than 1, shouldn't happen.")
        i = 0
        while i < 10:
            try:
                f = open(SCHEMAFILE, 'w')
                #custom separators to get rid of spaces and save some file size
                json.dump(page, f, separators=(',',':'))
                f.close()
            except IOError:
                i += 1
                continue
            break
        if len(self.qualities) != len(result['qualities']):
            self.qualities = range(len(result['qualities']))
        for q in result['qualities']:
            self.qualities[result['qualities'][q]] = result['qualityNames'].get(q, q)
        if len(self.origins) != len(result['originNames']):
            self.origins = range(len(result['originNames']))
        for origin in result['originNames']:
            #TODO: convert strings to numbers elsewhere
            self.origins[origin['origin']] = origin['name']
        for i in result['items']:
            self.items[i['defindex']] = i
        for a in result['attributes']:
            self.attributes[a['defindex']] = a

class Inventory(object):
    def __init__(self, playerid, schema=None):
        if not schema:
            schema = Schema()
        self.schema = schema
        self.player = playerid
        try:
            int(playerid)
        except ValueError:
            playerid = resolve_vanity(playerid)
        page = geturl(getinvurl, steamid=playerid, **basevals)
        if page == None:
            raise SteamAPITimeout("Couldn't retrieve player inventory")
        result = page['result']
        status = result['status']
        if status != 1:
            raise SteamAPIError(INVERRORS[status])
        #why change it to map()? because it's cooler, that's why
        self.items = map(lambda i: Item(schema, i), result['items'])
        #for item in result['items']:
        #    self.items.append(Item(schema, item))

    def search(self, levels=[], qualities=[], name='', name_exact='', slots=[],
               classes=[], exclude=[], defindex=[], origins=[], tradable=True,
               craftable=True):
        """
Search parameters:
levels: list containing item levels, e.g. [77,100]
qualities: list containing item quality names, e.g. ['vintage', 'genuine']
name: partial match string, e.g "key" for "Mann Co. Supply Crate Key"
name_exact: case-sensitive exact match for item name
slots:  list containing item slots, e.g. ['head', 'misc']
classes: list of classes which can use the item (OR, not AND), e.g. ['heavy']
exclude: list of specific defindices or item names to exclude from the search
defindex: list of specific defindices to search for, e.g. [743]
origins: list of item origins (either numerical index or name)
         to accept, e.g. [0] or ['timed'] for drop only
tradable: only list tradable items (default True)
craftable: only list craftable items (default True)
"""
        for i in xrange(len(qualities)):
            qualities[i] = qualities[i].lower()
        for i in xrange(len(slots)):
            slots[i] = slots[i].lower()
        retval = []
        o = []
        for origin in origins:
            if isinstance(origin, str):
                try:
                    origin = int(origin)
                except ValueError:
                    o.append(origin.lower())
                    continue
            try:
                o.append(self.schema.origins[origin].lower())
            except IndexError:
                pass
        for item in self.items:
            if item['item_name'] in exclude or item['defindex'] in exclude:
                continue
            if defindex and not item['defindex'] in defindex:
                continue
            if levels and not item['level'] in levels:
                continue
            if qualities and not item['qualityName'].lower() in qualities:
                continue
            if name and not name.lower() in item['item_name'].lower():
                continue
            if name_exact and name_exact != item['item_name']:
                continue
            if slots and not item['slot'].lower() in slots:
                continue
            if o and not item['originName'].lower() in o:
                continue
            if tradable and not item['tradable']:
                continue
            if craftable and not item['craftable']:
                continue
            if classes:
                for cls in classes:
                    if item.usable_by_class(cls):
                        break
                else:
                    continue
            retval.append(item)
        return retval
