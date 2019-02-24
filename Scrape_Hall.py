import requests
import smtplib
import json
import yaml
from datetime import datetime
from datetime import timedelta
from bs4 import BeautifulSoup
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def get_next_week():
    last_successful_date = open('./last_week').read()
    year, month, date = (int(x) for x in last_successful_date.split(', '))
    date = datetime(year, month, date)
    return date + timedelta(days=7)


def get_menu(date=datetime.now(), week_offset=0):
    """ Gets the menu for the week of the specified date plus the offset.
    Returns None if the menu isn't there
    """ 

    # Work out the URL to scrape
    w = date.strftime('%w')
    date = date - timedelta(days=int(w))
    date = date + timedelta(weeks=week_offset)
    url_date = date.strftime('%d-%b').lower()

    url = 'http://intranet.joh.cam.ac.uk/hall-menu-' + url_date

    request = requests.get(url)

    data = []
    html = BeautifulSoup(request.text, 'html.parser')
    menu_table = html.find('table')

    # Check to see if the menu has been uploaded yet
    if menu_table is None:
        return None

    menu_table = menu_table.find('tbody')
    rows = menu_table.find_all('tr')

    for row in rows:
        cols = row.find_all('td')
        current_row = {}

        # Get the date from each row of the table
        date_col = cols[0].find_all('p')
        day = date_col[0].get_text(strip=True)
        month = date_col[1].get_text(strip=True)
        current_row['date'] = day + ' ' + month

        # Get the menu from each row of the table
        courses = cols[1].find_all('p')
        courses = list(filter(lambda x: len(x) > 0, map(lambda x : x.get_text(strip=True), courses)))
        courses[1] = courses[1].replace('Vegetarian:', '')
        menu = {'Starter': courses[0], 'Vegetarian': courses[1], 'Main': courses[2], 'Sides': courses[3], 'Dessert': courses[4]}
        current_row['menu'] = menu
        data.append(current_row)

    return data, date


def value_in_any_of(value, list_to_check):
    return any([all([word in value.lower() for word in full.split()]) for full in list_to_check])


def find_interesting_days(menu, desires, disgusts):
    interesting_days = []
    for day in menu:
        for c, v in day['menu'].items():
            # Check if the the day has any desired menu items
            if value_in_any_of(v, desires):
                # Check that the day does not contain any disgusts
                if disgusts is not None and not value_in_any_of(v, disgusts):
                    if len(interesting_days) == 0 or interesting_days[-1]['date'] != day['date']:
                        interesting_days.append(day)

    return interesting_days


def generate_email_body(name, interesting_days):
    msg = 'Hi ' + name + ',<br><br>'

    if len(interesting_days) == 0:
        msg = msg + "Unfornunately, I haven't found anything good at hall this week. I'll try again next week!<br><br>"
    else:
        msg = msg + "According to your desires, you may like the following:<br><br>"

        for day in interesting_days:
            msg = msg + '<b>' + day['date'] + '</b><br>'
            menu = day['menu']
            for course, dish in menu.items():
                msg = msg + '<i>' + course + '</i>: ' + dish + '<br>'

            msg = msg + '<br>'

    msg = msg + 'Yours sincerely,<br>HallBot'
    return msg


def send_email(interesting_days, destination, name):
    with open("keys.yaml", 'r') as stream:
        key_data = yaml.load(stream)

        fromaddr = key_data['email_address']
        toaddr = destination
        msg = MIMEMultipart()
        msg['From'] = 'HallBot' + '<' + fromaddr + '>'
        msg['To'] = toaddr
        msg['Subject'] = "Weekly Hall Digest"

        body = generate_email_body(name, interesting_days)
        msg.attach(MIMEText(body, 'html'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(fromaddr, key_data['password'])
        text = msg.as_string()
        server.sendmail(fromaddr, toaddr, text)
        server.quit()


def run():
    menu, date = get_menu(date=get_next_week())

    json_data = open('./users.json').read()
    users = json.loads(json_data)

    for u in users:
        i_d = find_interesting_days(menu, u['desires'], u['disgusts'])
        send_email(i_d, u['email'], u['name'])

    # Update last_week file
    file = open('last_week', 'w')
    file.write(date.strftime("%Y, %m, %d"))
    file.close()


if __name__ == "__main__":
    run()
