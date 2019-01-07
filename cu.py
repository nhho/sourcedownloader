from contextlib import closing
import filecmp
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
                         'Chrome/65.0.3325.181 Safari/537.36'}
RETRY_CNT = 10
TIMEOUT = 10  # 10 sec


def download(file_path, url, auth):
  for i in range(RETRY_CNT):
    print url[url.rfind('/') + 1:].encode('ascii', 'replace')[:78],
    try:
      if url.startswith('ftp'):
        with closing(urllib2.urlopen(url)) as conn:
          with open(file_path, 'wb') as local_file:
            shutil.copyfileobj(conn, local_file)
      else:
        with requests.get(url, auth=auth, stream=True, headers=HEADERS,
                          timeout=TIMEOUT) as req:
          req.raise_for_status()
          req.raw.decode_content = True
          with open(file_path, 'wb') as local_file:
            shutil.copyfileobj(req.raw, local_file)
      print '\r' + ' ' * 78 + '\r',
      return True
    except RequestException as err:
      print '\r' + ' ' * 78 + '\r',
      if i == 0 and isinstance(err, SSLError) and url.startswith('https'):
        url = 'http' + url[5:]
        return download(file_path, url, auth)
      if i == RETRY_CNT - 1:
        print err
        return False
      # print 'retry %d' % (i + 1)


def readable_file_size(file_size, suffix='B'):
  for unit in ['', 'Ki', 'Mi']:
    if abs(file_size) < 1024:
      return "%.2f%s%s" % (file_size, unit, suffix)
    file_size /= float(1024)
  return "%.2f%s%s" % (file_size, 'Gi', suffix)


def get_url_and_suffix(tag, base_url, pure_url):
  url = tag['href']
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


def get_file_name(url, file_name_set):
  file_name = url[url.rfind('/') + 1:]
  if '?' in file_name:
    file_name = file_name[:file_name.find('?')]
  while file_name in file_name_set:
    print 'REPEATED', file_name, url
    dot = file_name.rfind('.')
    file_name = file_name[:dot] + '_' + file_name[dot:]
  return file_name


def get_file_set(folder):
  file_list = [entry for entry in os.listdir(folder)
               if os.path.isfile(os.path.join(folder, entry))]
  return set(file_list)


def prepare_root_folder():
  if os.path.exists('old_output'):
    print 'Remove folder [old_output]'
    shutil.rmtree(u'old_output')
  if os.path.exists('output'):
    print 'Rename folder [output] to [old_output]'
    os.rename('output', 'old_output')
  print 'Create folder [output]'
  os.makedirs('output')


def save_pw(folder, auth):
  with open(folder + '/pw.txt', 'w') as pw_file:
    for line in auth:
      pw_file.write(line + '\n')


def compare(folder):
  old_folder = 'old_' + folder
  if not os.path.exists(old_folder):
    print 'New folder [%s] (does not exist in folder [old_output])' % folder
    return
  old_files = get_file_set(old_folder)
  new_files = get_file_set(folder)
  for file_name in old_files - new_files:
    print 'File [%s] no longer exists' % file_name
  for file_name in new_files - old_files:
    print 'New file [%s]' % file_name
  for file_name in new_files & old_files:
    if not filecmp.cmp(os.path.join(old_folder, file_name),
                       os.path.join(folder, file_name)):
      print 'Differences found in file [%s]' % file_name


def main():  # pylint: disable=too-many-locals
  prepare_root_folder()
  for folder, urls, auth in FOLDER_URL:   # noqa # pylint: disable=too-many-nested-blocks
    folder = os.path.join(*folder)
    print '=== %s ===' % folder
    folder = os.path.join('output', folder)
    os.makedirs(folder)
    if auth is not None:
      save_pw(folder, auth)
    url_set = set()
    file_name_set = set(['pw.txt'])
    total_file_size = 0
    for ind, url in enumerate(urls):
      total = 1
      pure_url = url[:url.rfind('/') + 1]
      base_url = url[:url.replace('//', '__').find('/')]
      url_set.add(url)
      homepage_name = 'homepage'
      if len(urls) > 1:
        homepage_name += str(ind + 1)
      homepage_name += '.html'
      file_name_set.add(homepage_name)
      file_path = os.path.join(folder, homepage_name)
      download(file_path, url, auth)
      total_file_size += os.stat(file_path).st_size
      with requests.get(url, auth=auth, stream=True, headers=HEADERS) as req:
        req.raise_for_status()
        req.raw.decode_content = True
        with open(file_path, 'wb') as homepage_file:
          shutil.copyfileobj(req.raw, homepage_file)
      req = requests.get(url, auth=auth, headers=HEADERS)
      req.raise_for_status()
      for tag in BeautifulSoup(req.text, 'html.parser',
                               parse_only=SoupStrainer('a')):
        if tag.has_attr('href'):
          url_and_suffix = get_url_and_suffix(tag, base_url, pure_url)
          if url_and_suffix is None:
            continue
          download_url, suffix = url_and_suffix
          if download_url in BLACKLIST or download_url in url_set:
            continue
          file_name = get_file_name(download_url, file_name_set)
          if suffix in SUFFIX or download_url in WHITELIST:
            url_set.add(download_url)
            # print ' ' + file_name
            file_name_set.add(file_name)
            file_path = os.path.join(folder, file_name)
            if download(file_path, download_url, auth):
              total_file_size += os.stat(file_path).st_size
              total += 1
          elif suffix not in SUFFIX_IGNORE:
            print 'UNEXPECTED SUFFIX', file_name, download_url
      print '%d %s from %s' % (total, 'file' if total == 1 else 'files', url)
    print 'total %s' % readable_file_size(total_file_size)
    compare(folder)


if __name__ == '__main__':
  main()
