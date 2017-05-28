import pymongo
from analyze import Status

class Db(object):
    def __init__(self):
        self.client = pymongo.MongoClient()
        self.table = self.client.rain.rain
        
    def _idkey(self, key):
        return {"_id": key}
    
    def _getValue(self, key):
        result = self.table.find_one(self._idkey(key))
        if result:
            result = result[key]
        return result
    
    def _setValue(self, key, value):
        self.table.find_one_and_replace(self._idkey(key), {key: value}, upsert=True)
    
    def getStatus(self):
        status = self._getValue("status")
        if status is None or len(status) == 0:
            return None
        return Status(status["start"], status["end"], status["type"])
    
    def setStatus(self, status):
        if status is None:
            doc = {}
        else:
            doc = {'start': status.start, 'end': status.end, 'type': status.type}
        self._setValue("status", doc)
            
    def getHash(self):
        return self._getValue("hash")
    
    def setHash(self, h):
        self._setValue("hash", h)
    
    def getUsers(self):
        users = self._getValue("users")
        if users is None:
            self.table.insert(self._idkey("users"), {'users': []})
            return []
        return users
    
    def addUser(self, user):
        self.getUsers()
        self.table.find_one_and_update(self._idkey("users"), {"$addToSet": {'users': user}})
        
    def removeUser(self, user):
        self.getUsers()
        self.table.find_one_and_update(self._idkey("users"), {"$pull": {'users': user}})
        
        


