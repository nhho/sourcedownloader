import os
import shutil

import requests
from bs4 import BeautifulSoup, SoupStrainer


FOLDER_URL = [  # (folder, [links], (id, pw))
    ('CSCI3130/1718_sem1', ['https://www.cse.cuhk.edu.hk/~siuon/csci3130/'], None)
]
SUFFIX = set(['doc', 'docx', 'ppt', 'pptx', 'pdf', 'zip', 'rar', 'gz', 'm', 'txt'])
SUFFIX_IGNORE = set(['com', 'hk', 'htm', 'html', 'asp', 'php'])
WHITELIST = set([])
BLACKLIST = set([])
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
                  '(KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36'
}

suffix_set = set()
for folder, urls, auth in FOLDER_URL:
    if '/' in folder:
        pure_folder = folder[:folder.find('/')]
    else:
        pure_folder = folder
    print '[%s]' % pure_folder
    if os.path.exists(pure_folder):
        shutil.rmtree(pure_folder)
    os.makedirs(folder)
    if auth is not None:
        with open(folder + '/pw.txt', 'w') as f:
            for line in auth:
                f.write(line + '\n')
    link_set = set()
    file_name_set = set(['pw.txt'])
    for at, url in enumerate(urls):
        total = 1
        pure_url = url[:url.rfind('/') + 1]
        base_url = url[:url.replace('//', '__').find('/')]
        homepage_name = 'homepage'
        if len(urls) > 1:
            homepage_name += str(at + 1)
        with requests.get(url, auth=auth, stream=True, headers=HEADERS) as req:
            req.raise_for_status()
            with open(folder + '/' + homepage_name + '.html', 'wb') as f:
                shutil.copyfileobj(req.raw, f)
        req = requests.get(url, auth=auth)
        req.raise_for_status()
        for tag in BeautifulSoup(req.text, 'html.parser', parse_only=SoupStrainer('a')):
            if tag.has_attr('href'):
                link = tag['href']
                if '.' in link:
                    suffix = link[link.rfind('.') + 1:].lower()
                    if '/' not in suffix:
                        if '?' in suffix:
                            suffix = suffix[:suffix.find('?')]
                        suffix_set.add(suffix)
                        if not link.startswith('http'):
                            if link.startswith('/'):
                                link = base_url + link
                            else:
                                link = pure_url + link
                        file_name = link[link.rfind('/') + 1:]
                        if link in BLACKLIST:
                            continue
                        if suffix in SUFFIX or link in WHITELIST:
                            if link in link_set:
                                continue
                            link_set.add(link)
                            if file_name in file_name_set:
                                print ' REPEATED', file_name, link
                                continue
                            file_name_set.add(file_name)
                            # print ' ' + file_name
                            with requests.get(link, auth=auth, stream=True, headers=HEADERS) as r:
                                r.raise_for_status()
                                with open(folder + '/' + file_name, 'wb') as f:
                                    shutil.copyfileobj(r.raw, f)
                            total += 1
                        elif suffix not in SUFFIX_IGNORE:
                            print ' UNEXPECTED SUFFIX', file_name, link
        print ' total:', total
# print 'suffix_set:', suffix_set
