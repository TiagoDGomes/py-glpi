# py-glpi


## Code examples ##

* Start:
```python
from glpi import *
glpi = GLPI(url_rest="https://url-glpi/apirest.php", 
            user_token="your_user_token",
            app_token='your_app_token',
            )
```
* Get computers:
```python
computers = glpi.computers.filter(name='My PC')
computers = glpi.computers.filter(mac_address='10:23:45:c6:d7:e8')
for computer in computers:
    print (computer)
```

* Advanced search computers
```python
my_criteria = GLPISearchCriteria(
    logical_operator=GLPISearchCriteria.LINK_LOGICAL_OPERATOR_AND,
    itemtype=GLPISearchCriteria.ITEM_TYPE_COMPUTER,
    searchtype=GLPISearchCriteria.SEARCH_TYPE_CONTAINS,
    value='My PC',
    field=SearchItemManager.fields['name'],
)
my_criteria.add_rule(    
    logical_operator=GLPISearchCriteria.LINK_LOGICAL_OPERATOR_AND,
    itemtype=GLPISearchCriteria.ITEM_TYPE_COMPUTER,
    searchtype=GLPISearchCriteria.SEARCH_TYPE_CONTAINS,
    value='10:23:45:c6:d7:e8',
    field=SearchItemManager.fields['mac_address'],
)
computers = glpi.computers.filter(criteria=my_criteria)
for computer in computers:
    print (computer)
```
