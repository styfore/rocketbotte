from dataclasses import dataclass, field
from datetime import datetime
from dateutil import parser
from enum import Enum
from tkinter.font import ROMAN

from colorama import init

@dataclass(init=False)
class User():
    id: str
    username: str
    name: str
    
    def __init__(self, json:dict):
        self.id = json.get('_id')
        self.username = json.get('username')
        self.name = json.get('name')

@dataclass(init=False)
class Message():
    id: str
    rid: str
    tmid: str
    msg: str
    u: User
    ts: datetime
    updated_at: datetime

    def __init__(self, json:dict):
        self.id = json.get('_id')
        self.rid = json.get('rid')
        self.tmid = json.get('tmid')
        self.msg = json.get('msg')
        self.u = User(json.get('u'))
        self.ts = parser.parse(json.get('ts'), datetime.ut)
        self.updated_at = parser.parse(json.get('updated_at'))
        print(self.content, self.ts, self.updated_at ,  json.get('ts'))
        
    @property
    def author(self) -> User:
        return self.u
    
    @property
    def roomId(self) -> str:
        return self.rid

    @property
    def threadId(self) -> str:
        return self.tmid
    
    @property
    def content(self) -> str:
        return self.msg
    @property
    def created_at(self)  -> datetime:
        return self.ts

subscription_type = {'d' : 'dm', 'c' : 'channels', 'p': 'groups'}
class RoomType(Enum):

    C = 'c'
    D = 'd'
    P = 'p'
    
    @property
    def endpoint(self) -> str:
        return subscription_type(self.value)
    
@dataclass(init=False)
class Suscription:
    _id: str
    rid: str
    t: RoomType
    name: str
    fname: str
    u: User
    ts: datetime
    ls: datetime
    lr: datetime
    updated_at: datetime

    def __init__(self, json:dict):
        self.id = json.get('_id')
        self.rid = json.get('rid')
        self.t = RoomType(json.get('t'))
        self.name = json.get('name')
        self.fname = json.get('fname')
        self.u = User(json.get('u'))
        
        self.ts = parser.parse(json.get('ts'))
        self.ls = parser.parse(json.get('ls'))
        self.lr = json.get('lr')
        self.updated_at = json.get('updated_at')
        print(self.best_name, 'ts', self.ts, 'ls', self.ls, 'lr', self.lr)
    
    @property
    def user(self) -> User:
        return self.u
    
    @property
    def roomId(self) -> str:
        return self.rid
    
    @property
    def last_seen_activity(self) -> datetime:
        return self.ls
    
    @property
    def last_reply(self) -> datetime:
        return self.lr
    
        
    @property
    def room_type(self) -> RoomType:
        return self.t
    
    @property
    def best_name(self) -> str:
        return self.fname if self.fname is not None else self.name
    
    
    


