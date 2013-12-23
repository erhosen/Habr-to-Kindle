#!/usr/bin/env python
# encoding: utf-8

import grab
import os
import sqlite3 as lite
from lxml import etree
from lxml.builder import E
from urllib import urlretrieve
from shutil import rmtree, copy2
from subprocess import call
from string import punctuation

# TODO: more documentation
# TODO: REWRITE drop_tag. Delete spoilers and habracuts

# for example: '/Users/linustorvalds/KindleGen/kindlegen' in Mac
# or 'C:\KindleGen\klindlegen.exe' in Windows
KINDLEGEN_PATH = '/Users/vladimirvazoveckov/KindleGen/kindlegen'

# 0.5mb ~95% of all images in habr.
MAX_PIC_WEIGHT = 512000 # 500 kB

# -c0: without compression
# -c1: standart DOC
# -c2: huffdic compression for Kindle
COMPRESS_FORMAT = '-c2'

DELETE_HTML_FILE = True

def create_folder(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def prepare_name(name):
    return ''.join([ch for ch in name if not(ch in punctuation)])

#def drop_tag(self):
#    parent = self.getparent()
#    assert parent is not None
#    previous = self.getprevious()
#    if self.text and isinstance(self.tag, basestring):
#        # not a Comment, etc.
#        if previous is None:
#            parent.text = (parent.text or '') + self.text
#        else:
#            previous.tail = (previous.tail or '') + self.text
#    if self.tail:
#        if len(self):
#            last = self[-1]
#            last.tail = (last.tail or '') + self.tail
#        elif previous is None:
#            parent.text = (parent.text or '') + self.tail
#        else:
#            previous.tail = (previous.tail or '') + self.tail
#    index = parent.index(self)
#    parent[index:index+1] = self[:]

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
        except Exception,e:
            print 'failed to load image from %s' % img.get('src')
            print e

    for obj in html.xpath('//*[self::iframe or self::object]'):
        obj.getparent().replace(obj, E.img( {'src': 'images/obj_dummy.gif'}))

def create_mobi_file(html_filename, path):
    try:
        call([KINDLEGEN_PATH, html_filename, COMPRESS_FORMAT])
        if DELETE_HTML_FILE:
            os.remove(html_filename)
            rmtree(path + 'images/')
    except OSError, e:
        print 'Wrong path to kindlegen; not generating .mobi version'
        print e

def save_content(post, article_filename, path):
    html = E.html({ "xmlns": 'http://www.w3.org/1999/xhtml', "{http://www.w3.org/XML/1998/namespace}lang" : 'en', "lang": 'en' },
        E.head( E.meta( { 'http-equiv' : 'Content-Type', 'content' : 'http://www.w3.org/1999/xhtml; charset=utf-8' } ),
            E.title( post['title'] ),
            E.meta( { 'name': 'author', 'content' : post['author']} ),
            E.meta( { 'name': 'description', 'content' : post['title']} ) ),
        post['body'] )

    replace_objects(html, path)

    with open(article_filename, "w") as page_fp:
        page_fp.write( etree.tostring(html, pretty_print=True) )

    create_mobi_file(article_filename, path)

def get_content(g, link, path='files/'):
    g.go(link)
    if g.response.code == 404:
        return 'Page not found, or something wrong with habr'
    else:
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

        save_content(post, article_filename, path)

        print article_filename, 'ok'

def get_favorites(username):
    path_to_folder = 'files/favs_' + username + '/'
    create_folder(path_to_folder)
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
                get_content(g, link, path=path_to_folder)
            print 'Result in', path_to_folder

def get_data_from_db(cur, hub):
    path_to_folder = 'files/hub_' + hub + '/'
    create_folder(path_to_folder)
    g = grab.Grab()
    number_of_articles = raw_input('How much articles do you want? (0 - all): ')
    modes = {'1' : 'Score', '2' : 'Comments', '3' : 'Favs'}
    if number_of_articles == '0':
        cur.execute("SELECT * FROM %s" % (hub))
    else:
        sorting_mode = raw_input('What sorting mode? ("1 - rating", "2 - comments", "3 - favorites"): ')
        cur.execute("SELECT * FROM %s ORDER BY %s DESC LIMIT %s" % (hub, modes[sorting_mode], number_of_articles))
    for post in (elem for elem in cur.fetchall()):
        get_content(g, post[3], path=path_to_folder)
    print 'Result in', path_to_folder

if __name__ == '__main__':
    print 'habr_to_kindle ver.0.3 via ErhoSen 2013'
    print 'Choose mode:'
    print '1 - from hub'
    print '2 - from favorites'
    print '3 - from url'
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
        g = grab.Grab()
        get_content(g, raw_input('link to article (for example "http://habrahabr.ru/post/206916/"): '))
        print 'Result in files/'