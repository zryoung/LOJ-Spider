

from util import request_get


host = 'https://cemc.uwaterloo.ca/'
url = host + 'ajax'
params = {
    "grade":20,
    "academic_year":"All",
    "contest_category":29,
    "view_name":"listing",
    "view_display_id":"past_contest",
}
headers={
    "Cookie": "SSESSd51f0751c2e4bacf872f152c09e2bbb0=HSTlAxiqrSfJC%2CO%2CIY6sb8DKZWMqptTcaU7qGwcc4DK44DC0",
    "host": host,
    "Content-Type": "application/json",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.18 Safari/537.36 Edg/93.0.961.10",
}

result = request_get(url,params=params,headers=headers)
print(result)