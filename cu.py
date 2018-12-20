import os
import shutil

from bs4 import BeautifulSoup, SoupStrainer
import requests


FOLDER_URL = [  # (folder, [links], (id, pw))
    ('CSCI3130/1819-sem1',
     ['https://www.cse.cuhk.edu.hk/~siuon/csci3130/'],
     None)
]
SUFFIX = set(['doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'pdf', 'zip', 'rar',
              'gz', 'm', 'java', 'scala', 'txt', 'sql', 'asm'])
SUFFIX_IGNORE = set(['com', 'hk', 'htm', 'html', 'asp', 'php'])
WHITELIST = set([])
BLACKLIST = set([])
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                         'AppleWebKit/537.36 (KHTML, like Gecko) '
                         'Chrome/65.0.3325.181 Safari/537.36'}


def download(file_path, url, auth):
  with requests.get(url, auth=auth, stream=True, headers=HEADERS) as req:
    req.raise_for_status()
    req.raw.decode_content = True
    with open(file_path, 'wb') as local_file:
      shutil.copyfileobj(req.raw, local_file)


def readable_file_size(file_size, suffix='B'):
  for unit in ['', 'Ki', 'Mi']:
    if abs(file_size) < 1024:
      return "%.2f%s%s" % (file_size, unit, suffix)
    file_size /= float(1024)
  return "%.2f%s%s" % (file_size, 'Gi', suffix)


def get_url_and_suffix(tag, base_url, pure_url):
  url = tag['href']
  if '.' not in url:
    return None
  suffix = url[url.rfind('.') + 1:].lower()
  if '/' in suffix:
    return None
  if '?' in suffix:
    suffix = suffix[:suffix.find('?')]
  if '#' in suffix:
    suffix = suffix[:suffix.find('#')]
  if not url.startswith('http'):
    if url.startswith('/'):
      url = base_url + url
    else:
      url = pure_url + url
  return (url, suffix)


def get_file_name(url, file_name_set):
  file_name = url[url.rfind('/') + 1:]
  while file_name in file_name_set:
    print 'REPEATED', file_name, url
    dot = file_name.rfind('.')
    file_name = file_name[:dot] + '_' + file_name[dot:]
  return file_name


def prepare_folder(folder):
  if '/' in folder:
    pure_folder = folder[:folder.find('/')]
  else:
    pure_folder = folder
  print '=== %s ===' % pure_folder
  if os.path.exists(pure_folder):
    shutil.rmtree(pure_folder)
  os.makedirs(folder)


def save_pw(folder, auth):
  with open(folder + '/pw.txt', 'w') as pw_file:
    for line in auth:
      pw_file.write(line + '\n')


def main():  # pylint: disable=too-many-locals
  for folder, urls, auth in FOLDER_URL:
    prepare_folder(folder)
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
      file_path = folder + '/' + homepage_name
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
            file_path = folder + '/' + file_name
            download(file_path, download_url, auth)
            total_file_size += os.stat(file_path).st_size
            total += 1
          elif suffix not in SUFFIX_IGNORE:
            print 'UNEXPECTED SUFFIX', file_name, download_url
      print '%d file(s) from %s' % (total, url)
    print 'total %s' % readable_file_size(total_file_size)


if __name__ == '__main__':
  main()
