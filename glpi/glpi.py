from requests import Request, Session
import json
import warnings
import copy
import sys 


warnings.filterwarnings("ignore")


FIELDS_SEARCH_COMMON = dict(
    name=1,
    id=2,
    entity_name=80,
)   

   
FIELDS_SEARCH_COMPUTER = dict(
    location_complete_name=3,
    otherserial=6,
    status_name=31,
    model_name=40,
    mac_address=21,
)   


FIELDS_SEARCH_TICKET = dict(
    urgency=3,
    users_id_recipient=4,
)


class GLPIItem(object):
    glpi = None
    item_type = None
    save_data = {}
    _f_filter = None
    _updated = False

    def __init__(self, data, glpi, item_type, f_filter=False):
        self.__dict__.update(data)
        self.glpi = glpi
        self.item_type = item_type
        self._f_filter = f_filter
        self._updated = False

    def __getattr__(self, key):
        if self._f_filter and not self._updated:
            field_id = str(FIELDS_SEARCH_COMMON['id'])
            if field_id in self.__dict__:
                item_id = self.__dict__[field_id]
            else:
                item_id = self.__dict__[u'id']
            refresh_data = self.glpi.__getattribute__(self.item_type.lower() + 's').get(item_id, raw_data=True)
            self.__dict__.update(refresh_data)   
            self._updated = True 
        try:
            return self.__dict__[key]
        except KeyError:         
            rel_id = self.__dict__['{0}_id'.format(key)]            
            if isinstance(rel_id, int):
                if rel_id == 0:
                    return []    
                return self.glpi.__getattribute__(key).get(rel_id)
            else:           
                criteria = GLPISearchCriteria()
                for v in rel_id:            
                    criteria.add_rule(
                        logical_operator=GLPISearchCriteria.LINK_LOGICAL_OPERATOR_OR,
                        itemtype=key,
                        field=2,
                        value=v,
                        searchtype=GLPISearchCriteria.SEARCH_TYPE_EQUALS,
                    )  
                return self.glpi.__getattribute__(key).filter(criteria=criteria)

    def __setattr__(self, key, value):
        if key in ['_data','glpi','save_data', 'item_type', '_f_filter', '_updated' ]:
            super(GLPIItem, self).__setattr__(key, value)
            return
        self.__dict__[key] = value
        self.save_data[key] = value

    def __str__(self):
        return str(self.__dict__)

    def __repr__(self):
        return str(self.__dict__)

    def save(self):
        data = {'input': self.save_data}
        result = self.glpi._get_json('/{key}/{item_id}'.format(key=self.item_type, item_id=self.id,), 'PUT', data)
        if isinstance(result, list):
            if 'message' in result[0] and result[0]['message'] != '':
                raise GLPIException(result[0]['message']) 


class SearchItemManager(object):
    item_type = None
    glpi = None
    all_fields = FIELDS_SEARCH_COMMON.copy()
    def __init__(self, item_type, glpi, fields={}):
        self.item_type = item_type
        self.glpi = glpi 
        self.fields = fields
        self.fields.update(FIELDS_SEARCH_COMMON)
        self.all_fields.update(fields)

    def _get_forcedisplay(self):        
        forcedisplay = ''
        count = 0
        for _, value in self.fields.items():
            forcedisplay += '&forcedisplay[{0}]={1}'.format(count, value)
            count += 1
        return forcedisplay
    
    def all(self):
        return self.filter()
    
    def filter(self, criteria=None, raw_data=False, *args, **kwargs): 
        if not criteria:
            criteria = GLPISearchCriteria()
            for k, v in kwargs.items():            
                criteria.add_rule(
                    logical_operator=GLPISearchCriteria.LINK_LOGICAL_OPERATOR_AND,
                    itemtype=self.item_type,
                    field=self.fields[k],
                    value=v,
                    searchtype=GLPISearchCriteria.SEARCH_TYPE_CONTAINS,
                )                   
        result = self.glpi._get_json(
            '/search/{key}/?expand_drodpowns=true&range=0-1000&{criteria}{forcedisplay}'.format(
                key=self.item_type,
                criteria=criteria.to_url_param(),
                forcedisplay=self._get_forcedisplay(),
                )
            )
        self.glpi._debug("\nSearchItemManager.filter: {0}".format(str(result)))
        
        if raw_data:
            return result

        glpiitems = []
        if result['count'] > 0:            
            for item in result['data']:
                for k, v in self.fields.items():
                    if str(v) in item:
                        item[k] = item[str(v)] 
                glpiitems.append(GLPIItem(item, self.glpi, self.item_type, f_filter=True))            
        return glpiitems
                   

    def get(self, item_id, raw_data=False,):
        result = self.glpi._get_json('/{key}/{item_id}'.format(key=self.item_type, item_id=item_id,) )
        self.glpi._debug("\nSearchItemManager.get:  {0}".format(str(result)))
        if raw_data:
            return result
        if isinstance(result, list):
            self.glpi._debug("\nSearchItemManager.get Error: " + str(result[1]))
            raise GLPIException(result[1]) 
        r = GLPIItem(result, self.glpi, self.item_type, f_filter=False)
        return r


class GLPI(object): 
    debug = False 
    def __init__(self, url_rest, user_token, app_token):
        self.url_rest = url_rest
        self.user_token = user_token
        self.app_token = app_token
        self.tickets = SearchItemManager('Ticket', self,FIELDS_SEARCH_TICKET)
        self.computers = SearchItemManager('Computer', self, FIELDS_SEARCH_COMPUTER)
        self.states = SearchItemManager('State', self,)
        self.locations = SearchItemManager('Location', self,)
        self.domains = SearchItemManager('Domain', self,)
        self.manufacturers = SearchItemManager('Manufacturer', self,)
        self.computermodels = SearchItemManager('ComputerModel', self,)
        self.networks = SearchItemManager('Network', self,)
        self.entities = SearchItemManager('Entity', self,)
        self.calendars = SearchItemManager('Calendar', self,)
        self._session = None

    def _get_session(self):
        if not self._session:
            url_init_session = self.url_rest + "/initSession"
            req = Request('GET', url_init_session)
            self._session = Session()
            self._session.headers.update({'Content-Type': 'application/json'})
            self._session.headers.update({'Authorization': 'user_token ' + self.user_token})
            self._session.headers.update({'App-Token':  self.app_token })
            prepped = self._session.prepare_request(req)
            resp = self._session.send(prepped,verify=False,)
            result = json.loads(resp.text)
            if isinstance(result, list):
                raise GLPISessionErrorException(result[1])
            _session_token = result['session_token']            
            self._session.headers.update({'Session-Token': _session_token})
        return self._session

    def _get_json(self, url, method='GET',data=None):
        full_url = self.url_rest + url
        self._debug('\nFetch URL: ' + full_url + '\n')
        if data is None:
            req = Request(method, full_url)
        elif isinstance(data, str):
            req = Request(method, full_url, data)
        else:    
            req = Request(method, full_url, json=data)        
        s = self._get_session()    
        prepped = s.prepare_request(req)
        resp = s.send(prepped,verify=False)
        result = json.loads(resp.text)        
        return result

    def _debug(self, text):
        if self.debug:
            print("\n")
            print(text)  


class GLPIException(Exception):
    pass


class GLPISessionErrorException(GLPIException):
    pass

    
class GLPISearchCriteria(object):
    LINK_LOGICAL_OPERATOR_AND = 'AND'
    LINK_LOGICAL_OPERATOR_AND_NOT = 'AND NOT'
    LINK_LOGICAL_OPERATOR_OR = 'OR'
    SEARCH_TYPE_CONTAINS = 'contains'
    SEARCH_TYPE_EQUALS = 'equals'
    SEARCH_TYPE_NOT_EQUALS = 'notequals'
    SEARCH_TYPE_LESS_THAN = 'lessthan'
    SEARCH_TYPE_MORE_THAN = 'morethan'
    SEARCH_TYPE_UNDER = 'under'
    SEARCH_TYPE_NOT_UNDER = 'notunder'
    ITEM_TYPE_COMPUTER = 'Computer'
    ITEM_TYPE_TICKET = 'Ticket'
    ITEM_TYPE_STATE = 'State'
    ITEM_TYPE_DOMAIN = 'Domain'
    ITEM_TYPE_COMPUTER_MODEL = 'ComputerModel'
    ITEM_TYPE_MANUFACTURER = 'Manufacturer'
    ITEM_TYPE_NETWORK = 'Network'
    ITEM_TYPE_ENTITY = 'Entity'
    ITEM_TYPE_CALENDAR = 'Calendar'

    def __init__(self, logical_operator=None, itemtype=None, searchtype=None, value=None, field=SearchItemManager.all_fields['name']):
        self.rules = []
        if logical_operator and itemtype and searchtype and value:
            self.add_rule(logical_operator, itemtype, searchtype, value, field)        
        
    def add_rule(self, logical_operator, itemtype, searchtype, value, field=SearchItemManager.all_fields['name']):
        self.rules.append({
            'link': logical_operator,
            'itemtype': itemtype,
            'field': field,
            'searchtype' : searchtype,
            'value': value,
        })

    def to_url_param(self):
        result = ''
        count = 0
        for rule in self.rules:
            for item, value in rule.items():
                result += '&criteria[{0}][{1}]={2}'.format(count, item, value)
            count += 1
        return result

    def __str__(self):
        return str(self.rules)
