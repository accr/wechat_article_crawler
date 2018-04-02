# -*- coding: utf-8 -*-  
from scrapy.http.cookies import CookieJar
import xml.etree.ElementTree as ET
import re
import copy
import json
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import urllib
import urllib2
import logging
from lxml import etree
import MySQLdb
import re
from cStringIO import StringIO
from PIL import Image
import hashlib
import time
import yaml
import datetime
import oss2
import sys

db = MySQLdb.connect(host = "47.97.175.80", user = "crawler", passwd = "123456", db = "crawler", port = 3306, charset='utf8')
cursor = db.cursor()
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
i_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/30.0.1599.69 Safari/537.36",
                "Accept": "text/xml,application/xml,application/xhtml+xml,text/html;q=0.9,text/plain;q=0.8,image/png,image/jpeg,image/gif;q=0.2,*/*;q=0.1"}

class subImgUrl():

    def __init__(self):
        pass

    def engine(self):
        sql = """select * from wechat_text where is_sub = 0 limit 1"""
        cursor.execute(sql)
        article_data = cursor.fetchone()
        cms_list = []
        article_content = article_data[10]
        weixin_name = article_data[6]
        article_title = article_data[4]
        article_id = article_data[0]
        selector = etree.HTML(article_content)
        tree_list = selector.xpath('.//*')
        tree_id = 1
        for node in tree_list:
            cms_node = {}
            if (node.tag == 'p' and len(node.xpath('.//img')) == 0):
                # p标签作为文本入库
                p_string = ET.tostring(node, encoding = 'utf-8', method = 'xml')
                cms_node['data'] = p_string
                cms_node['type'] = 1
                tree_id += 1
                pass
            elif (node.tag == 'img'):
                # 图片入库
                img_string = node.xpath('.//@src')[0]
                # 规则处理图片路径
                if type(img_string) == unicode:
                    img_string = img_string.encode('utf-8')
                res = requests.get(img_string, headers = i_headers, timeout = 30, verify = False)
                img_body = res.content
                img_RAM = StringIO(img_body)
                img_RAM.seek(0)
                try:
                    orig_image = Image.open(img_RAM)
                    width, height = orig_image.size
                except Exception as e:
                    print 'Open Image failed!'
                    continue
                # 获取图片的长和宽
                strinfo = re.compile(r'https://mmbiz.qpic.cn/mmbiz_*[a-zA-Z]*/(.*?)/([0-9]*).*')
                url_pre = str.format(r'/wechat_article_img_new/{0}/',weixin_name)
                article_content_sub = strinfo.sub(url_pre+r'\1_\2.jpg',img_string)
                if article_content_sub is None or width == 0 or height == 0:
                    continue
                cms_node['data'] = {}
                cms_node['data']['path'] = article_content_sub
                cms_node['type'] = 2
                cms_node['data']['width'] = width
                cms_node['data']['height'] = height
                # 获取处理后的路径
                tree_id += 1
                pass
            if cms_node:
                cms_list.append(cms_node)
        result_data = {'cover_image':{}}
        result_data['status'] = 0
        result_data['title'] = article_title.encode('utf-8')
        result_data['founder_id'] = 53
        result_data['cover_image']['path'] = 'wechat_article_img_new/nowre_official/U1Zib5mDgHfuPN8e5lQckk1Fotiaxcd8VY8ISCsdjcgu3TUN0XDwWqHRJPLic1JYJhjC74ibic3kOibSnfqBUHj0UM8g_640.jpg'
        result_data['cover_image']['height'] = 400
        result_data['cover_image']['width'] = 400
        result_data['detail_list'] = cms_list
        # for each in cms_list:
        #     print each
        #     print '========================='

        # 请求接口将数据入库
        login_data = self.login_request()
        self.cms_request(result_data,login_data)
        # self.update_article(article_id)


    def login_request(self):
        try:
            response = requests.post(
                url="http://tcommunityapi.ofashion.com.cn/blogger/login",
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                },
                data=json.dumps({
                    "username": "13121221233",
                    "password": "123456",
                    "country_code": "86",
                    "source": "42"
                })
            )
            content = json.loads(response.content)
        except requests.exceptions.RequestException:
            print('HTTP Request failed')
        return content['data']

    def cms_request(self,cms_data,login_data):
        url_cms = "http://tcommunityapi.ofashion.com.cn/feed/editArticleFeed"
        access_token = login_data['access_token'].encode('utf-8')
        params_list = []
        login_id = login_data['blogger_info']['blogger_id']
        cms_data['nounce'] = 999
        
        sign_get = self.get_sign(login_id,access_token)
        sign_post = self.post_sign(cms_data,access_token)
        cms_data['sign'] = sign_post
        # for each in cms_data['detail_list']:
        #     print each
        #     print "====================="
        cms_data = json.dumps(cms_data, encoding = 'utf-8', ensure_ascii = False)
        url_fix = str.format('?source=42&login_id={0}&nounce=999&sign={1}',
            login_id,sign_get)
        try:
            response = requests.post(
                url=url_cms+url_fix,
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                },
                data=cms_data
            )
            print('Response HTTP Status Code: {status_code}'.format(
                status_code=response.status_code))
            print('Response HTTP Response Body: {content}'.format(
                content=response.content))
        except requests.exceptions.RequestException:
            print('HTTP Request failed')

    def post_sign(self,cms_data,access_token):
        items = cms_data.items()
        items.sort()
        params_list = []
        for each_parmas in items:
            params_list.append(str.format('{0}={1}',each_parmas[0],each_parmas[1]))
        params_str = '&'.join(params_list)
        sign = hashlib.md5(params_str+access_token+'ofashion'+'999').hexdigest()
        return sign

    def get_sign(self,login_id,access_token):
        sign = str.format('login_id={0}&nounce=999&source=42{1}ofashion999',login_id,access_token)
        print sign
        sign = hashlib.md5(sign).hexdigest()
        return sign

    def update_article(self, article_id):
        sql_update = """UPDATE wechat_text set is_sub = 1 where id = '%d'""" % (article_id)
        cursor.execute(sql_update)
        db.commit()
        print 'article is processed'

if __name__ == '__main__':
    test = subImgUrl()
    test.engine()
    # test.login_request()