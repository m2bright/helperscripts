import sys

__author__ = 'michaelbright'
import re
import getopt
import datetime
from dateutil.parser import parse
import requests
from requests.auth import HTTPBasicAuth
import simplejson as json
from operator import itemgetter, attrgetter

config = {
    'server': None,
    'repository': 'libs-snapshot-local',
    'dryRun': False,
    'user': None,
    'pass': None,
    'maven_group': None,
    'time_delay': 45
}

opts, args = getopt.getopt(sys.argv[1:], 's:r:dg:t:', ['server=', 'repository=', 'dryRun', 'group=', 'time_delay='])
for opt, arg in opts:
    if opt in ('-s', '--server'):
        config['server'] = arg
    elif opt in ('-r', '--repository'):
        config['repository'] = arg
    elif opt in ('-d', '--dryRun'):
        config['dryRun'] = True
    elif opt in ('-u', '--user'):
        config['user'] = arg
    elif opt in ('-p', '--pass'):
        config['pass'] = arg
    elif opt in ('-g', '--group'):
        config['maven_group'] = arg
    elif opt in ('-t', '--time_delay'):
        config['time_delay'] = int(arg)

if not config['maven_group']:
    print "You must provide the group please use -g or --group to define."
    sys.exit(1)

class DictHolder(dict):
    pass


class Artifactory:

    def __init__(self, config):
        self.config = config

    def _request(self, path):
        return requests.get("{0}{1}".format(config['server'], path))

    def print_repositories(self):
        resp = self._request('/artifactory/api/repositories')
        if 200 != resp.status_code:
            print "Error:{0}".format(resp.raw)
            sys.exit(1)

        for json_data in resp.json():
            print "key :{0}\n\ttype:{1}\n\tdescription:{2}\n\turl:{3}\n".format(json_data['key'],json_data['type'],json_data['description'],json_data['url'])

    def folder_info(self, path):
        response = self._request('/artifactory/api/storage/{0}/{1}'.format(self.config['repository'], path))
        if 200 != response.status_code:
            print "Error: problem getting folder info for: {0}. status: {1}".format(path, response.status_code)
            sys.exit(1)
        return response.json()

    def remove_child(self, child):
        json_data = self.folder_info(child.full_path)
        if parse(json_data['lastUpdated']).date() < (datetime.date.today() - datetime.timedelta(days=self.config['time_delay'])):
            url = "{0}{1}/{2}".format(self.config['server'], '/artifactory/' + self.config['repository'], child.full_path)
            if not self.config['dryRun']:
                response = requests.delete(url, auth=HTTPBasicAuth(self.config['user'], self.config['pass']))
                if response.status_code == 200 or response.status_code == 204:
                    print "Deleted {0} - last updated on:{1}".format(child.full_path, json_data['lastUpdated'])
                else:
                    print "Failed to delete {0} - returned with {1}".format(child.full_path, response.status_code)
            else:
                print "requests.delete(\"{0}{1}/{2}\")".format(self.config['server'], '/artifactory/' + self.config['repository'], child.full_path)
        else:
            print "{0} was not older than 45 days.".format(child.full_path)

    def is_artifact_folder(self, child):
        return "-SNAPSHOT" in child['uri']

    def get_artifact_folders(self):
        path = self.config['maven_group']
        children = []
        json_data = self.folder_info(path)
        for child in json_data['children']:
            if child['folder']:
                if self.is_artifact_folder(child):
                    child_holder = DictHolder(child)
                    first_sort = re.sub(r'[-.]', '', path)
                    second_sort = int(re.sub(r'[^\d]+', '', child['uri']))
                    full_path = path + child['uri']

                    setattr(child_holder, 'first_sort', first_sort)
                    setattr(child_holder, 'second_sort', second_sort)
                    setattr(child_holder, 'full_path', full_path)

                    children.append(child_holder)
                else:
                    if not 'ro-scripts' in child['uri']:
                        children = children + self.get_artifact_folders(path + child['uri'])
        return children


artifactory = Artifactory(config)
children = artifactory.get_artifact_folders()
children.sort(key=attrgetter('first_sort', 'second_sort'))


count = 0
left_over = []
to_be_removed = []
current_repository = None

for child in children:
    if current_repository is None:
        current_repository = child.first_sort

    if current_repository == child.first_sort:
        to_be_removed.append(child)
        count += 1
    elif current_repository != child.first_sort:
        if count > 0:
            left_over.append(to_be_removed.pop())
            if count >= 2:
                left_over.append(to_be_removed.pop())
        count = 0
        current_repository = child.first_sort
        to_be_removed.append(child)

print "Left Over\n-----------------------\n"
for left in left_over:
    print left.full_path
print "-----------------------\nRemove\n------------------\n"
for remove in to_be_removed:
    artifactory.remove_child(remove)
