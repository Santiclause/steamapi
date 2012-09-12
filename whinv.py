import steamapi as steam
from threading import Thread
from Queue import Queue
import time

#clean item drop quality indices.
CLEAN = [0, 1, 2, 3, 5, 7, 8, 9, 10, 12, 13, 14, 15, 20, 21]

TF2WHBOTNAMES = {'76561198049572592': 'solidbeetle', '76561198050360350': 'punchypear',
                 '76561198049617266': 'formidablecenturion', '76561198049577280': 'dervishdevil',
                 '76561198049602279': 'raucousraisin', '76561198066901870': 'spitefulspoon',
                 '76561198049570579': 'maliciousghost', '76561198050405490': 'prudentlime',
                 '76561198049565327': 'maxshort', '76561198049569823': 'pricelesspea',
                 '76561198049564447': 'beautifulbutterfly', '76561198049572568': 'leapinglion',
                 '76561198049576830': 'principledpenguin', '76561198066912582': 'villainousvisitor',
                 '76561198049566349': 'lastfan', '76561198050393767': 'screamingpineapple',
                 '76561198049605011': 'bizarreburger', '76561198049582702': 'gentlehelper',
                 '76561198049615010': 'superiorspook', '76561198049615070': 'stealthshadow',
                 '76561198049616166': 'injuriousicicle', '76561198050405562': 'lastlemon',
                 '76561198049623464': 'leathallunch', '76561198049617774': 'shockingshrimp',
                 '76561198049602325': 'pedanticpickle', '76561198049570201': 'lethalninja',
                 '76561198049603157': 'overwhelmingelephant', '76561198049610491': 'talentedturtle',
                 '76561198049602177': 'balefulballoon', '76561198049614998': 'perniciouspencil',
                 '76561198049603887': 'majestictrout', '76561198049615230': 'deadlydoctor',
                 '76561198049565263': 'fortunatefig', '76561198049570439': 'taintedassassin',
                 '76561198049615186': 'damagingdrum', '76561198066912810': 'wrathfulwrench',
                 '76561198049572574': 'astonishingflames', '76561198066190432': 'nefariousnoise',
                 '76561198049914683': 'livingorange', '76561198049604903': 'intimidatingfairy'}
class AdvancedTimer(Thread):
    def __init__(self, timeout, func):
        Thread.__init__(self)
        self._wait = Event()
        self.timeout = timeout
        self.func = func

    def run(self):
        t = 0.0
        s = 0.0
        while not self._wait.wait(s - t):
            #dynamic wait interval to account for varying function execution times
            s = time.time() + self.timeout
            self.func()
            t = time.time()

    def stop(self):
        self._wait.set()
        
class WarehouseInventory(steam.Inventory):
    def __init__(self, schema=None):
        if not schema:
            schema = steam.Schema()
        self.schema = schema
        self.update()

    def update(self):
        self.items = []
        self.schema.update()
        queue = Queue()
        output = Queue()
        errors = Queue()
        def worker():
            while queue.unfinished_tasks:
                item = queue.get()
                try:
                    inv = steam.Inventory(item, schema)
                except steam.SteamAPIError, e:
                    queue.put(item)
                    queue.task_done()
                    continue
                except:
                    errors.put(item)
                    queue.task_done()
                    continue
                #this map adds a 'bot' key to the item dictionary, so that you
                #can track the bot that each item came from
                map(lambda i: i.__setitem__('bot', item), inv.items)
                output.put(inv.items)
                queue.task_done()
        ids = map(lambda x: long(x), TF2WHBOTNAMES.keys())
        for i in ids:
            queue.put(i)
        #let's say 5 workers
        for x in xrange(5):
            t = Thread(target=worker)
            t.daemon = True
            t.start()
        queue.join()
        while output.qsize():
            self.items += output.get()

def getbot(item):
    return TF2WHBOTNAMES[str(item['bot'])]

if __name__ == "__main__":
    schema = steam.Schema()
    wh = WarehouseInventory(schema)
