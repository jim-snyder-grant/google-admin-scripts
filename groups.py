#!/usr/bin/python

# started from code from Ransom, and then changed it to not recursively query groups in groups

HELP = "Extracts the emails from every group list in a given domain.\n\
        Usage: python groups.py DOMAIN [CSV] [TEXT]  \n\
        DOMAIN - the domain to use, e.g mydomain.com\n\
        optional output format arguments: \n\
        TEXT (default) output as text\n\
        CSV output as CSV\n\
        "

import enum
import json
import os
import pickle
import sys

import google_auth_oauthlib
from google.auth.transport.requests import AuthorizedSession, Request
from google_auth_oauthlib.flow import InstalledAppFlow
from requests_oauthlib import OAuth2Session

#DOMAIN, name of the domain to work with 
#DOMAIN = ''  

# CLIENT_SECRETS, name of a file containing the OAuth 2.0 information for this
# application, including client_id and client_secret, which are found
# on the API Access tab on the Google APIs
# Console <http://code.google.com/apis/console>
CLIENT_SECRETS = 'client_secrets.json'


def get_creds():
  scopes = ['https://www.googleapis.com/auth/admin.directory.group.member.readonly',
            'https://www.googleapis.com/auth/admin.directory.group.readonly']

  creds = None
  if os.path.exists('token.pickle'):
    with open('token.pickle', 'rb') as token:
      creds = pickle.load(token)
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      creds.refresh(Request())
    else:
      flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, scopes=scopes)
      creds = flow.run_local_server()
    # Save the credentials for the next run
    with open('token.pickle', 'wb') as token:
      pickle.dump(creds, token)
  return creds

class Group:
  class GroupType(enum.Enum):
    Unknown = 0
    Group = 1
    Alias = 2
    User = 3
    Empty = 4
  def __init__(self, group_json):
    self.name = group_json['name']
    self.email = group_json['email']
    self.description = group_json['description']
    self.type = Group.GroupType.Unknown
    self.emails = {self.email}
    if 'aliases' in group_json:
      self.add_aliases(group_json['aliases'])
    self.members = set()

  def add_aliases(self, aliases: list[str]):
    self.emails.update(aliases)

def create_groups(session, domain):
  r = session.get('https://admin.googleapis.com/admin/directory/v1/groups', 
                  params={'domain': domain, 'maxResults': 5000})
     
  json_groups = r.json()['groups'] 

  groups = {}
  for g in json_groups:
    if g['name'] == 'everyone':
      continue
    group = Group(g)
    group.type = Group.GroupType.Group
    if (0 == int(g['directMembersCount'])):
        group.type = Group.GroupType.Empty
    groups[g['email']] = group
  return groups

def handle_aliases(groups):
  for g in [g for g in groups.values() if g.type == Group.GroupType.Alias]:
    assert(len(g.members) == 1)
    target_email = next(iter(g.members))
    if not target_email in groups:
      # Reference to a user - this is actually a one member group
      g.type = Group.GroupType.Group
      continue

    target = groups[target_email]
    if target.type == Group.GroupType.Alias:
      raise Exception('Alias to Alias not supported')
    elif target.type == Group.GroupType.Group:
      target.add_aliases(g.emails)
    else:
      # Target is a user - this is a one member group
      g.type = Group.GroupType.Group

def list_group_members(session, groups, group):

  if group.members:
    # members already listed
    return
  r = session.get('https://admin.googleapis.com/admin/directory/v1/groups/{group_id}/members'.format(group_id=group.email))
  if (group.type == Group.GroupType.Empty):
      json_members = [{'email' : '(empty group)'}]
  else:
      json_members = r.json()['members']
  for member in json_members:
    member_email = member['email']
    if member_email in groups:
      target_group = groups[member_email]
      if target_group.type == Group.GroupType.Group:
            member_email = '~' + member_email  
    group.members.add(member_email.lower())

def list_members(session, groups):
  for g in [g for g in groups.values() if g.type in {Group.GroupType.Group,Group.GroupType.Empty}] :
    list_group_members(session, groups, g)

def print_groups(groups, domain, useCSV, useTEXT):

    if useCSV:
        with open(domain+'.list.csv', 'w') as fCSV:
            for g in [g for g in groups.values() if g.type in {Group.GroupType.Group,Group.GroupType.Empty}]:
                for member in sorted(g.members):
                    print(member + "," + g.name,file=fCSV)
            print("created and filled " + fCSV.name)
    if useTEXT:       
        with open(domain+'.list.txt', 'w') as fTXT:
            for g in [g for g in groups.values() if g.type in {Group.GroupType.Group,Group.GroupType.Empty}]:
                print (g.name, file=fTXT)
                if g.description:
                    print(g.description, file=fTXT)
                print(sorted(g.emails),file=fTXT)
                for member in sorted(g.members):
                    print(member,file=fTXT)
                print("",file=fTXT)
            print("created and filled " + fTXT.name)
      
def main(argv):
    
    sample = open('samplefile.txt', 'w')
    print('GeeksForGeeks', file = sample)
    sample.close()
    
    
    argc = len(argv)
    if 1 == argc:
        print(HELP)
        exit(0)
    
    domain = argv[1]
    print("Domain: " + domain)
    hasCSV =  "CSV" in argv
    hasTEXT = "TEXT" in argv
#TEXT is the default     
    if not hasTEXT and not hasCSV:
        hasTEXT = True
    if (hasTEXT):
        print("using text format")
    if (hasCSV):
        print("using csv format")
    
    session = AuthorizedSession(get_creds())
    groups = create_groups(session, domain)
#    handle_aliases(groups)    
    list_members(session, groups)
    print_groups(groups, domain, hasCSV, hasTEXT)

if __name__ == '__main__':
  main(sys.argv)
