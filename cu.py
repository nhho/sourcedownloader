from contextlib import closing
import filecmp
import json
import os
import shutil
import urllib2

from bs4 import BeautifulSoup, SoupStrainer
from requests.exceptions import RequestException, SSLError
import requests


FOLDER_URL = [  # (folder, [links], (id, pw))
    (['CSCI3130', '1819-sem1'],
     ['https://www.cse.cuhk.edu.hk/~siuon/csci3130/'],
     None)
]
SUFFIX = set(['doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'pdf', 'zip', 'rar',
              'gz', 'm', 'java', 'scala', 'txt', 'sql', 'asm', 'tex', 'ps',
              'py', 'ipynb'])
SUFFIX_IGNORE = set(['com', 'hk', 'htm', 'html', 'asp', 'php', 'org', 'cn',
                     'shtml'])
WHITELIST = set([])
BLACKLIST = set([])
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                         'AppleWebKit/537.36 (KHTML, like Gecko) '
                         'Chrome/73.0.3683.103 Safari/537.36'}
RETRY_CNT = 10
TIMEOUT = 60  # 60 sec
PIAZZA_MAIN_URL = 'https://piazza.com'
PIAZZA_LOGIN_URL = 'https://piazza.com/class'
PIAZZA_URL_PATTERN = 'https://piazza.com/class_profile/get_resource/%s/%s'
PIAZZA_EMAIL = ''
PIAZZA_PASSWORD = ''
PIAZZA_RESOURCE_PREFIX = 'https://piazza.com/class_profile/get_resource/'


def readable_file_size(file_size, suffix='B'):
  for unit in ['', 'Ki', 'Mi']:
    if abs(file_size) < 1024:
      return "%.2f%s%s" % (file_size, unit, suffix)
    file_size /= float(1024)
  return "%.2f%s%s" % (file_size, 'Gi', suffix)


def get_file_set(folder):
  file_list = [entry for entry in os.listdir(folder)
               if os.path.isfile(os.path.join(folder, entry))]
  return set(file_list)


def get_url_and_suffix(url, pure_url, base_url):
  if url.startswith('mailto:'):
    return None
  if '.' not in url:
    return None
  suffix = url[url.rfind('.') + 1:].lower()
  if '/' in suffix:
    return None
  if '?' in suffix:
    suffix = suffix[:suffix.find('?')]
  if '#' in suffix:
    suffix = suffix[:suffix.find('#')]
  if not url.startswith('http') and not url.startswith('ftp'):
    if url.startswith('/'):
      url = base_url + url
    else:
      url = pure_url + url
  return (url, suffix)


def get_urls_from_html(file_path):
  with open(file_path, 'r') as homepage_file:
    html = homepage_file.read()
  for tag in BeautifulSoup(html, 'html.parser', parse_only=SoupStrainer('a')):
    if tag.has_attr('href'):
      yield tag['href']


def get_piazza_urls_from_html(file_path, session):
  with open(file_path, 'r') as homepage_file:
    for line in homepage_file:
      if 'this.network' in line:
        line = line[line.index('{'):]
        line = line[:line.rindex('}') + 1]
        course_data = json.loads(line)
        course_id = course_data['id']
        sections = course_data['config']['resource_sections']
        for section in sections:
          resources = section.get('ordering', [])
          for resource_id in resources:
            resource_url = PIAZZA_URL_PATTERN % (course_id, resource_id)
            with session.get(resource_url, headers=HEADERS,
                             allow_redirects=False,
                             timeout=TIMEOUT) as req:
              if req.status_code == 302:
                yield req.headers['Location']
        break


class Course(object):

  def __init__(self, folder, urls, auth):
    self.urls = urls
    self.auth = auth
    folder = os.path.join(*folder)
    print '=== %s ===' % folder
    self.folder = os.path.join('output', folder)
    os.makedirs(self.folder)
    self.url_set = set()
    self.file_name_set = set([])
    if self.auth is not None:
      self.file_name_set.add('pw.txt')
      pw_path = os.path.join(self.folder, 'pw.txt')
      with open(pw_path, 'w') as pw_file:
        for line in self.auth:
          pw_file.write(line + '\n')
    self.total_file_size = 0

  def download(self, file_path, url, session=None):
    for i in range(RETRY_CNT):
      print url[url.rfind('/') + 1:].encode('ascii', 'replace')[:78],
      try:
        if url.startswith('ftp'):
          with closing(urllib2.urlopen(url)) as conn:
            with open(file_path, 'wb') as local_file:
              shutil.copyfileobj(conn, local_file)
        else:
          if session is None:
            session = requests
          with session.get(url, auth=self.auth, stream=True, headers=HEADERS,
                           timeout=TIMEOUT) as req:
            req.raise_for_status()
            req.raw.decode_content = True
            with open(file_path, 'wb') as local_file:
              shutil.copyfileobj(req.raw, local_file)
        self.total_file_size += os.stat(file_path).st_size
        print '\r' + ' ' * 78 + '\r',
        return True
      except RequestException as err:
        print '\r' + ' ' * 78 + '\r',
        if i == 0 and isinstance(err, SSLError) and url.startswith('https'):
          url = 'http' + url[5:]
          return self.download(file_path, url)
        if i == RETRY_CNT - 1:
          print err
          return False
        # print 'retry %d' % (i + 1)

  def get_file_name(self, url):
    file_name = url[url.rfind('/') + 1:]
    if '?' in file_name:
      file_name = file_name[:file_name.find('?')]
    while file_name in self.file_name_set:
      print 'REPEATED', file_name, url
      dot = file_name.rfind('.')
      file_name = file_name[:dot] + '_' + file_name[dot:]
    return file_name

  def handle_url(self, url, pure_url=None, base_url=None):
    url_and_suffix = get_url_and_suffix(url, pure_url, base_url)
    if url_and_suffix is None:
      return False
    download_url, suffix = url_and_suffix
    if download_url in BLACKLIST or download_url in self.url_set:
      return False
    file_name = self.get_file_name(download_url)
    if suffix in SUFFIX or download_url in WHITELIST:
      self.url_set.add(download_url)
      # print ' ' + file_name
      self.file_name_set.add(file_name)
      file_path = os.path.join(self.folder, file_name)
      if self.download(file_path, download_url):
        return True
    elif suffix not in SUFFIX_IGNORE:
      print 'UNEXPECTED SUFFIX', file_name, download_url
    return False

  def process(self):
    for ind, url in enumerate(self.urls):
      total = 1
      pure_url = url[:url.rfind('/') + 1]
      base_url = url[:url.replace('//', '__').find('/')]
      self.url_set.add(url)
      homepage_name = 'homepage'
      if len(self.urls) > 1:
        homepage_name += str(ind + 1)
      homepage_name += '.html'
      self.file_name_set.add(homepage_name)
      file_path = os.path.join(self.folder, homepage_name)
      if url.startswith(PIAZZA_MAIN_URL):
        session = requests.Session()
        with session.get(PIAZZA_MAIN_URL, headers=HEADERS,
                         timeout=TIMEOUT) as req:
          req.raise_for_status()
        login_data = {
            'from': '/signup',
            'email': PIAZZA_EMAIL,
            'password': PIAZZA_PASSWORD,
            'remember': 'on'
        }
        with session.post(PIAZZA_LOGIN_URL, headers=HEADERS, data=login_data,
                          timeout=TIMEOUT) as req:
          req.raise_for_status()
        self.download(file_path, url, session)
        for resource_url in get_piazza_urls_from_html(file_path, session):
          if self.handle_url(resource_url):
            total += 1
      else:
        self.download(file_path, url)
        for resource_url in get_urls_from_html(file_path):
          if self.handle_url(resource_url, pure_url, base_url):
            total += 1
      print '%d %s from %s' % (total, 'file' if total == 1 else 'files', url)
    print 'total %s' % readable_file_size(self.total_file_size)

  def compare(self):
    old_folder = 'old_' + self.folder
    if not os.path.exists(old_folder):
      print 'New folder [%s] (does not exist in folder [old_output])' % \
          self.folder
      return
    old_files = get_file_set(old_folder)
    new_files = get_file_set(self.folder)
    for file_name in old_files - new_files:
      print 'File [%s] no longer exists' % file_name
    for file_name in new_files - old_files:
      print 'New file [%s]' % file_name
    for file_name in new_files & old_files:
      if not filecmp.cmp(os.path.join(old_folder, file_name),
                         os.path.join(self.folder, file_name)):
        print 'Differences found in file [%s]' % file_name


def prepare_root_folder():
  if os.path.exists('old_output'):
    print 'Remove folder [old_output]'
    shutil.rmtree(u'old_output')
  if os.path.exists('output'):
    print 'Rename folder [output] to [old_output]'
    os.rename('output', 'old_output')
  print 'Create folder [output]'
  os.makedirs('output')


def main():
  prepare_root_folder()
  for course_info in FOLDER_URL:
    course = Course(*course_info)
    course.process()
    course.compare()


if __name__ == '__main__':
  main()
