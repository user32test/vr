import requests
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.proxy import Proxy
from selenium.webdriver.common.proxy import ProxyType
from selenium.webdriver.common.by import By
import time
import re
import argparse
import datetime
from datetime import datetime
import calendar


#
#   Usage example:
#   sudo service tor start
#   ./vrsearch.sh --from Helsinki --to Kokkola --proxy 127.0.0.1:9050
#
#  Note: Make sure the place names start with upper case letter.
# 
#=---- Settings -------------------#

request_delay = 1;
geckodriver_path = "./geckodriver"

#----------------------------------#




parser = argparse.ArgumentParser(description="arguments");
parser.add_argument("--from");
parser.add_argument("--to");
parser.add_argument("--proxy");
parser.add_argument("--months");
parser.add_argument("-n");

args = parser.parse_args();

from_place = getattr(args, "from");
to_place = getattr(args, "to");

month_range_str = getattr(args, "months");
output_count_str = getattr(args, "n");

month_range = int(month_range_str);
output_count = int(output_count_str);

proxy_arg = getattr(args, "proxy");
if proxy_arg == None:
    print("Proxy should be used.");


# TODO: Cache this
rq = requests.get("https://nikita.tnnet.fi/~gumrak/Junat/liikennepaikat.html");
rqpage = rq.text;


if rqpage.find(from_place) < 0:
    print("'" + from_place + "' Not found!");
    exit();

# Find correspoding place names.
# (cursed regex section)

tmp1 = re.findall("(.*)\n(.*)\n(.*)("+from_place+")", rqpage)[0];
from_place_tag = re.findall("<STRONG>.*<", tmp1[0])[0];
from_place_tag = from_place_tag.lstrip("<STRONG>");
from_place_tag = from_place_tag.rstrip("</STRONG></FONT><").upper();

tmp2 = re.findall("(.*)\n(.*)\n(.*)("+to_place+")", rqpage)[0];
to_place_tag = re.findall("<STRONG>.*<", tmp2[0])[0];
to_place_tag = to_place_tag.lstrip("<STRONG>");
to_place_tag = to_place_tag.rstrip("</STRONG></FONT><").upper();


# UUID4 Key is needed for the website to search for ticket prices.
# It updates everytime for each session so it has to be automated.

TARGET_URL="https://www.vr.fi/?from=PTO&to=HKI";


profile = webdriver.FirefoxProfile();



opt = Options();
opt.proxy = Proxy({ 'proxyType': ProxyType.MANUAL, 'socksProxy': proxy_arg, 'socksVersion': 5 });
opt.add_argument("--headless");

driver = webdriver.Firefox(service=Service(geckodriver_path), options=opt);

# Confirm proxy configuration.
driver.get("https://check.torproject.org");
if driver.title != "Congratulations. This browser is configured to use Tor.":
    print("\033[31mProxy configuration failed!\033[0m");
    exit();

print("\033[32m\033[1m(Proxy configuration validated)...\033[0m");


old_title = driver.title;

driver.get(TARGET_URL);

while True:
    if driver.title != old_title:
        break;
    time.sleep(1);


print(f"From {from_place}({from_place_tag}) - To {to_place}({to_place_tag})");
print(". Retrieving Key");

# Note: These may need to be manually replaced if 'vr.fi' website updates them.
cookies_button_xpath = "/html/body/div/div/dialog/div/div[3]/button[3]";
search_button_xpath = "/html/body/main/div[2]/div/div/div[2]/div[2]/button";

time.sleep(3);
print("|  Accepting only necessary cookies...");
cookie_button = driver.find_element(By.XPATH, cookies_button_xpath);
cookie_button.click();


time.sleep(1);
print("|  Searching...");
search_button = driver.find_element(By.XPATH, search_button_xpath);
search_button.click();

# Wait until change happens.
while True:
    if driver.current_url != TARGET_URL:
        break;
    time.sleep(1);
time.sleep(1);

key = re.findall("\\[key\\].*&", driver.current_url)[0];
key = key.lstrip("[key]=");
key = key.rstrip("&");

if len(key) != 36:
    print("'--> Key not found! \033[90m(try again?)\033[0m");
    exit();

print("'--> Key found: " + key);

# Key was found we can continue!

current_year = datetime.now().strftime("%Y");
current_month = datetime.now().strftime("%m");
current_day = datetime.now().strftime("%d");

        
#  'data_lines':
#   Each line represents information about the current trip.
#  <Departure time>|<Arrival time>|<Estimated time of the trip>|<Ticket price>|<Date>
data_lines = "";

for m in range(month_range):
    month_number = (int(current_month)-1 + m) % 12 + 1;
    days_in_month = calendar.monthrange(int(current_year), month_number)[1];
    start_day = 1;
    if m == 0:
        start_day = int(current_day);

    month_number_str = str(month_number);
    if month_number < 10:
        month_number_str = "0"+str(month_number);

    print("\n*---> Searching best prices for month: ("+month_number_str+")");
    for day_number in range(start_day, days_in_month+1):
        print(f"\033[0G\033[32m>  Progress: [{day_number}/{days_in_month}]\033[0m", end="");
        print("\033[A");


        URL = f"https://www.vr.fi/kertalippu-menomatkan-hakutulokset?from={from_place_tag}&to={to_place_tag}&passengers[0][key]={key}&passengers[0][type]=ADULT&outboundDate={current_year}-{month_number_str}-{day_number}";

        old_url = driver.current_url;
        driver.get(URL);
        
        timeout_timer = 0;
        while True:
            if driver.current_url != old_url:
                break;
            timeout_timer += 1;
            if timeout_timer > 10:
                print("\033[31m(Seems like the website is not responding or its very very slow)\033[0m");
                timeout_timer = 0;
            time.sleep(1);

        time.sleep(2); # Makes sure if the website responds very fast we should not miss any info.

        ptext = driver.find_element(By.XPATH, "/html/body/main/div[2]/div/div/div/div[2]/div[2]").text;
        #print(ptext);

        price_found = False;
        for line in ptext.splitlines():

            # Departure time.
            if 'ht' in line and 'aika' in line:
                if not price_found:
                    data_lines += "\n";
                data_lines += line.split(' ')[1]+"|";
                price_found = False;

            # Arrival time.
            if 'Saapumisaika' in line:
                data_lines += line.split(' ')[1]+"|";

            # Estimated time of the trip.
            if 'Matkan kesto' in line:
                data_lines += line.split(' ')[2]+line.split(' ')[3]+"|";
    
            # Ticket price and date.
            # The price is always at the bottom of each element text.
            if '€' in line:
                data_lines += line.split(' ')[0]+"|";
                data_lines += f"{current_year}-{month_number_str}-{day_number}";
                data_lines += "\n";
                price_found = True;

        #print("");
        #print(data_lines);
        #print("\033[90m< Waiting for 'request_delay' seconds >\033[0m");

        time.sleep(request_delay);


driver.quit();



# There may be some parts where it was unable to find the price for ticket.

data_array = data_lines.split('\n');
data_array_size = len(data_array)-1;

data_array_fixed = [];
data_size = 0;

for i in range(0, data_array_size):
    price_str = data_array[i].split('|');
    if len(price_str) != 5:
        continue;
    data_size += 1;
    data_array_fixed.append(data_array[i]);




# Note: Sorting could be improved in the future

for i in range(0, len(data_array_fixed)):
    price_A  = float(data_array_fixed[i].split('|')[3].replace(',','.', 1));

    for k in range(0, len(data_array_fixed)):
        price_B  = float(data_array_fixed[k].split('|')[3].replace(',','.', 1));

        if price_A < price_B:
            tmp = data_array_fixed[i];
            data_array_fixed[i] = data_array_fixed[k];
            data_array_fixed[k] = tmp;
    

print("\n");

for i in range(0, output_count):
    data_split = data_array_fixed[i].split('|');
    depart_time = data_split[0];
    arrive_time = data_split[1];
    trip_time = data_split[2];
    trip_price = data_split[3];
    trip_date = data_split[4];

    print(f"  [\033[35m\033[1m{trip_date}\033[0m]--------------\033[0m");
    print(f"  | Departure time: {depart_time}");
    print(f"  | Arrival time:   {arrive_time}");
    print(f"  | Trip time:      {trip_time}");
    print(f"  '---> \033[32m{trip_price}€\033[0m \n");





