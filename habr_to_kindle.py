#!/usr/bin/env python3
# encoding: utf-8

import os
import sqlite3 as lite
from lxml.html import parse
from lxml.builder import E
from lxml import etree
from urllib.request import urlretrieve
from shutil import rmtree, copy2
from subprocess import call
from string import punctuation

# TODO: more documentation
# TODO: Test on Windows
# TODO: OPF for hub, favs

# for example: '/Users/linustorvalds/KindleGen/kindlegen' in Mac
# or 'C:\KindleGen\kindlegen.exe' in Windows
KINDLEGEN_PATH = 'c:\kindlegen\kindlegen.exe'

# 0.5mb ~95% of all images in habr.
MAX_PIC_WEIGHT = 512000 # 500 kB

# -c0: without compression
# -c1: standart DOC
# -c2: huffdic compression for Kindle
COMPRESS_FORMAT = '-c0'

DELETE_HTML_FILE = False

def create_folder(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def prepare_name(name):
    return ''.join([ch for ch in name if not(ch in punctuation)])

def drop_tag(dtag):
    parent = dtag.getparent()
    assert parent is not None
    previous = dtag.getprevious()
    if dtag.text and isinstance(dtag.tag, str):
        # not a Comment, etc.
        if previous is None:
            parent.text = (parent.text or '') + dtag.text
        else:
            previous.tail = (previous.tail or '') + dtag.text
    if dtag.tail:
        if len(dtag):
            last = dtag[-1]
            last.tail = (last.tail or '') + dtag.tail
        elif previous is None:
            parent.text = (parent.text or '') + dtag.tail
        else:
            previous.tail = (previous.tail or '') + dtag.tail
    index = parent.index(dtag)
    parent[index:index+1] = dtag[:]

def replace_objects(html, path):
    img_folder = path + 'images/'
    create_folder(img_folder)
    copy2('gif_dummy.gif', img_folder)
    copy2('obj_dummy.gif', img_folder)

    for img in html.xpath('//img'):
        img_url = img.get('src')
        img_name = img_url.split('/')[-1]
        try:
            real_img = urlretrieve(img_url, img_folder + img_name)
            if int(real_img[1]['Content-Length']) > MAX_PIC_WEIGHT:
                img.set('src', 'images/gif_dummy.gif')
            else:
                img.set('src', 'images/' + img_name)
        except Exception as e:
            print('failed to load image from %s' % img.get('src'))
            print(e)

    for obj in html.xpath('//*[self::iframe or self::object]'):
        obj.getparent().replace(obj, E.img( {'src': 'images/obj_dummy.gif'}))

    for elem in html.xpath('//a'):
        drop_tag(elem)

    for elem in html.xpath('//div[@class="spoiler"]'):
        elem.find('./b[1]').append(E.br())
        drop_tag(elem.find('./div[1]'))
        drop_tag(elem)

def create_mobi_file(html_filename, path):
    try:
        call([KINDLEGEN_PATH, html_filename.encode('utf-8'), COMPRESS_FORMAT])
        if DELETE_HTML_FILE:
            os.remove(html_filename)
            rmtree(path + 'images/')
    except OSError as e:
        print('Wrong path to kindlegen; not generating .mobi version')
        print(e)

def save_content(post, article_filename, path):
    html = E.html({ "xmlns": 'http://www.w3.org/1999/xhtml', "{http://www.w3.org/XML/1998/namespace}lang" : 'en', "lang": 'en' },
        E.head( E.meta( { 'http-equiv' : 'Content-Type', 'content' : 'http://www.w3.org/1999/xhtml; charset=utf-8' } ),
            E.title( post['title'] ),
            E.meta( { 'name': 'author', 'content' : post['author']} ),
            E.meta( { 'name': 'description', 'content' : post['title']} ) ),
        post['body'] )

    replace_objects(html, path)

    with open(article_filename, "wb") as page_fp:
        page_fp.write( etree.tostring(html, pretty_print=True) )

    create_mobi_file(article_filename, path)

def get_content(link, path='files/'):
    try:
        post = {'title': None, 'body': None, 'author': None}

        data = parse(link)

        post['title'] = data.find('//h1[@class="title"]/span[@class="post_title"]').text
        try:
            post['author'] = data.find('//div[@class="author"]/a').text
        except: # TODO: test this error
            post['author'] = 'habrahabr'

        post_content = data.find('//div[@class="content html_format"]')
        post_rating = data.find('//div[@class="voting   "]/div/span[@class="score"]').text
        post_comments = data.findall('//div[@class="comment_body"]')

        post['body'] = E.body(E.h3(post['title']))

        post['body'].append(post_content)
        post['body'].append( E.p( E.b(post_rating + ' ' + post['author'])) )

        for comment in post_comments:
            com_class = comment.find('div[1]').get('class')
            if com_class == "author_banned":
                continue
            else:
                post['body'].append(E.hr())
            try:
                comment_author = comment.find('./div[1]/a[@class="username"]').text
                comment_rating = comment.find('./div[1]/div[@class="voting   "]/div[1]/span').text
            except AttributeError:
                continue
            comment_info = E.p( comment_rating + ' ' + comment_author)
            comment_body = comment.find('./div[2]')
            post['body'].append(comment_info)
            post['body'].append(comment_body)

        article_filename = path + prepare_name(post['title']) + '.html'

        save_content(post, article_filename, path)

        print(article_filename, 'ok')

    except IOError as e:
        print(e)

def get_favorites(username):
    path_to_folder = 'files/favs_' + username + '/'
    create_folder(path_to_folder)
    link_list = []

    def get_favs(url):
        fav_page = parse(url)
        next_page = fav_page.xpath('//a[@class="next" and @id="next_page"]')
        for elem in fav_page.xpath('//div[@class="posts shortcuts_items"]/div/h1/a[1]'):
            print('find:', elem.text, elem.get('href'))
            link_list.append(elem.get('href'))
        if len(next_page) > 0: get_favs('http://habrahabr.ru' + next_page[0].get('href'))

    try:
        get_favs('http://habrahabr.ru/users/' + username + '/favorites/')
        for link in (elem for elem in link_list):
            get_content(link, path=path_to_folder)
        print('Result in', path_to_folder)
    except IOError as e:
        print(e)
        return

def get_data_from_db(cur, hub):
    path_to_folder = 'files/hub_' + hub + '/'
    create_folder(path_to_folder)
    number_of_articles = input('How much articles do you want? (0 - all): ')
    modes = {'1' : 'Score', '2' : 'Comments', '3' : 'Favs'}
    if number_of_articles == '0':
        cur.execute("SELECT * FROM %s" % (hub))
    else:
        sorting_mode = input('What sorting mode? ("1 - rating", "2 - comments", "3 - favorites"): ')
        cur.execute("SELECT * FROM %s ORDER BY %s DESC LIMIT %s" % (hub, modes[sorting_mode], number_of_articles))
    for post in (elem for elem in cur.fetchall()):
        get_content(post[3], path=path_to_folder)
    print('Result in', path_to_folder)

if __name__ == '__main__':
    print('habr_to_kindle ver.0.4 via ErhoSen 2013')
    print('Choose mode:')
    print('1 - from hub')
    print('2 - from favorites')
    print('3 - from url')
    mode = ''
    while True:
        mode = input('Mode: ')
        if mode in ['1', '2', '3']: break
        else: print("Wrong mode, try again")
    if mode == '1':
        con = lite.connect('db/habra_hubs.db')
        cur = con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        for elem in (elem[0] for elem in cur.fetchall()):
            print(elem, end=' ')
        print('\n')
        hub = input('What hub are you interesting for? (for example "python"): ')
        get_data_from_db(cur, hub)
    elif mode == '2':
        get_favorites(input('Username: '))
    elif mode == '3':
        get_content(input('link to article (for example "http://habrahabr.ru/post/206916/"): '))
        print('Result in files/')
