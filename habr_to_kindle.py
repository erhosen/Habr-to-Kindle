#!/usr/bin/env python
# encoding: utf-8

import grab
import urllib
import sqlite3 as lite
from subprocess import call
import base64, mimetypes, urlparse
import sys
import os
from string import punctuation
from lxml.builder import E
from lxml import etree
import gif

# TODO: each hub to each folder
# TODO: something useful with output weight
# TODO: more documentation
# TODO: connect bd
# TODO: delete spoiler's and habracut

# for example: '/Users/linustorvalds/KindleGen/kindlegen'
KINDLEGEN_PATH = '/Users/vladimirvazoveckov/KindleGen/kindlegen'

# 1mb ~95% of all images in habr.
MAX_PIC_WEIGTH = 512000 # 500 kB

# -c0: without compression -c1: standart DOC -c2: huffdic compression for Kindle
COMPRESS_FORMAT = '-c0'

def data_encode_image(name,content):
    return u'data:%s;base64,%s' % (mimetypes.guess_type(name)[0], base64.standard_b64encode(content))

# For animated GIFs
GIF_DUMMY = data_encode_image('gif_dummy.gif', open('gif_dummy.gif').read())
OBJ_DUMMY = data_encode_image('obj-dummy.gif', open('obj-dummy.gif').read())

def create_mobi_file(html_filename):
    with open("/dev/null","w") as null:
        try:
            call([KINDLEGEN_PATH, html_filename, COMPRESS_FORMAT])
        except OSError, e:
            print 'Wrong path to kindlegen; not generating .mobi version'
            print e

def prepare_name(name):
    return ''.join([ch for ch in name if not(ch in punctuation)])

def is_remote(address):
    return urlparse.urlparse(address)[0] in ('http', 'https')

def resolve_path(target):
    base = 'http://habrahabr.ru/'
    if True:
        return urlparse.urljoin(base, target)

    if is_remote(target):
        return target

    if target.startswith('/'):
        if is_remote(base):
            protocol,rest = base.split('://')
            return '%s://%s%s' % (protocol, rest.split('/')[0], target)
        else:
            return target
    else:
        try:
            base, rest = base.rsplit('/', 1)
            return '%s/%s' % (base, target)
        except ValueError:
            return target

def replaceImages(html):
    for img in html.xpath('//img'):
        path = resolve_path(img.get('src'))
        try:
            if '.gif' == path[-4:]:
                gif_file = urllib.urlretrieve(path)
                if gif.GifInfo(gif_file[0], 1).frameCount > 1:
                    img.set('src', GIF_DUMMY)
                else:
                    real_img = urllib.urlopen(path)
                    img.set('src', data_encode_image(path.lower(),real_img.read()))
            else:
                real_img = urllib.urlopen(path)
                if int(real_img.info()['Content-Length']) > MAX_PIC_WEIGTH:
                    img.set('src', GIF_DUMMY)
                else:
                    img.set('src', data_encode_image(path.lower(),real_img.read()))
        except Exception,e:
            print 'failed to load image from %s' % img.get('src')
            print e

def replaceObj(html):
    while len(html.xpath('//iframe')) != 0:
        obj = html.xpath('//iframe')[0]
        obj.getparent().replace(obj, E.img( {'src': OBJ_DUMMY}))
    while len(html.xpath('//object')) !=0:
        obj = html.xpath('//object')[0]
        obj.getparent().replace(obj, E.img( {'src': OBJ_DUMMY}))

def save_content(post, article_filename):
    html = E.html({ "xmlns": 'http://www.w3.org/1999/xhtml', "{http://www.w3.org/XML/1998/namespace}lang" : 'en', "lang": 'en' },
        E.head( E.meta( { 'http-equiv' : 'Content-Type', 'content' : 'http://www.w3.org/1999/xhtml; charset=utf-8' } ),
            E.title( post['title'] ),
            E.meta( { 'name': 'author', 'content' : post['author']} ),
            E.meta( { 'name': 'description', 'content' : post['title']} ) ),
        post['body'] )

    replaceImages(html)
    replaceObj(html)

    with open(article_filename,"w") as page_fp:
        page_fp.write( etree.tostring(html,pretty_print=True) )

def get_content(link, path):
    g = grab.Grab()
    g.go(link)
    post = {'title': None, 'body': None, 'author': None}
    post['title'] = g.doc.select('//h1[@class="title"]/span[@class="post_title"]').text()
    try:
        post['author'] = g.doc.select('//div[@class="author"]/a').text()
    except grab.error.DataNotFound:
        post['author'] = 'habrahabr'

    post_content = g.doc.select('//div[@class="content html_format"]').node()
    post_rating = g.doc.select('//div[@class="voting   "]/div/span[@class="score"]').text()
    post_comments = g.doc.select('//div[@class="comment_body"]').node_list()

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

    save_content(post, article_filename)

    return article_filename

def get_article_from_url(url, path='files/'):
    html_filename = get_content(url, path)
    print html_filename, 'ok'
    create_mobi_file(html_filename)

def get_favorites(username):
    link_list = []
    g = grab.Grab()
    g.go('http://habrahabr.ru/users/' + username + '/favorites/')
    if g.response.code == 404:
        print 'User not found, or something wrong with habr'
        get_favorites(raw_input('Username: '))
    elif g.response.code == 200:
        nav = g.doc.select('//a[@class="next" and @id="next_page"]')
        for elem in g.doc.select('//div[@class="posts shortcuts_items"]/div/h1/a[1]'):
            print 'find:', elem.text(), elem.attr('href')
            link_list.append(elem.attr('href'))
        while nav.exists():
            g.go(nav.attr('href'))
            for elem in g.doc.select('//div[@class="posts shortcuts_items"]/div/h1/a[1]'):
                print 'find:', elem.text(), elem.attr('href')
                link_list.append(elem.attr('href'))
            nav = g.doc.select('//a[@class="next" and @id="next_page"]')
        else:
            for link in (elem for elem in link_list):
                get_article_from_url(link, path='files/favs/')
            print 'Result in files/favs/'

def get_data_from_db(cur, hub):
    number_of_articles = raw_input('How mamy articles do you want? ')
    sort_mode = raw_input('What sorting mode? ("rating", "comments", "Favs")')
    cur.execute("SELECT * FROM %s ORDER BY %s DESC LIMIT %s" % (hub, sort_mode, number_of_articles))
    for post in (elem for elem in cur.fetchall()):
        get_article_from_url(post[3], path='files/hub/')
        # TODO: folder for hub
    print 'Result in files/favs/'

if __name__ == '__main__':
    print 'habr_to_kindle ver.0.3 via ErhoSen 2013'
    print 'Choose mode:'
    print '1 - get N best(rating OR most commented OR most added to favorites) from hub'
    print '2 - get all articles from favorites'
    print '3 - get article from url'
    mode = ''
    while True:
        mode = raw_input('Mode: ')
        if mode in ['1', '2', '3']: break
        else: print "Wrong mode, try again"
    if mode == '1':
        con = lite.connect('db/habra_hubs.db')
        cur = con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        for elem in (elem[0] for elem in cur.fetchall()):
            print elem,
        print '\n'
        hub = raw_input('What hub are you interesting for? (for example "python"): ')
        get_data_from_db(cur, hub)
    elif mode == '2':
        get_favorites(raw_input('Username: '))
    elif mode == '3':
        get_article_from_url(raw_input('link to article (for example "http://habrahabr.ru/post/148940/"): '))