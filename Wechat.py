# -*- coding: utf-8 -*-  
from scrapy.http.cookies import CookieJar
import xml.etree.ElementTree as ET
import re
import copy
import json
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import urllib2
import logging
from lxml import etree
import MySQLdb
import re
from cStringIO import StringIO
from PIL import Image
import hashlib
import time
import datetime
import oss2

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
bucketname = "mstore"
AliyunAccessKey = "4y7f6sFaBorxMSDU"
AliyunSecretKey = "ODMIVC5Som1oEYJlxJxlJnrtrjZolk"
AliyunEndPoint = "https://oss-cn-beijing.aliyuncs.com"
db = MySQLdb.connect(host = "47.97.175.80", user = "crawler", passwd = "123456", db = "crawler", port = 3306)
cursor = db.cursor()

class Wechat_content():

    def __init__(self):
        pass

    def engine(self):
        
        sql = """select weixin_name,id,article_content from wechat_text where is_processed = 0 limit 1"""
        cursor.execute(sql)
        # 获取sql查询到的每条数据
        for each_text in cursor.fetchall():
            img_url_list = []
            article_content = each_text[2]
            article_id = each_text[1]
            weixin_name = each_text[0]
            selector = etree.HTML(article_content)
            p_tree_list = selector.xpath(".//p")
            img_id_insert = 0
            for p_tree_each in p_tree_list:
                if (p_tree_each.xpath(".//img") != []):
                    # 有图片 需要处理图片
                    for img_url_each in p_tree_each.xpath(".//img//@src"):
                        # 判断该图片是否已经处理
                        is_insert = self.is_insert(article_id, img_id_insert)
                        if is_insert == False:
                            img_url_list.append(img_url_each)
                            # 将图片url存入数据库
                            self.db_insert(article_id, weixin_name, img_id_insert, img_url_each)
                            img_id_insert += 1
                            pass
                else:
                    pass
                # 获取到每一个被处理完成的P标签
            # 调用图片的下载上传方法
            download_results = self.img_download(img_url_list,article_id)
            self.img_upload(download_results)
            self.update_article(article_id)



    def img_download(self,img_url_list,article_id):
        i_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/30.0.1599.69 Safari/537.36",
                "Accept": "text/xml,application/xml,application/xhtml+xml,text/html;q=0.9,text/plain;q=0.8,image/png,image/jpeg,image/gif;q=0.2,*/*;q=0.1"}
        results = []

        for img_id, img_url in enumerate(img_url_list):
            # 判断图片是否下载过
            # 实现代码
            img_data = {}
            if type(img_url) == unicode:
                img_url = img_url.encode('utf-8')
            res = requests.get(img_url, headers = i_headers, timeout = 30, verify = False)
            body = res.content
            img_RAM = StringIO(body)
            img_RAM.seek(0)
            # 生成一个Image对象（具体请看python PIL模块）
            orig_image = Image.open(img_RAM)
            # 根据图片格式生成后缀
            fmt = orig_image.format
            if fmt == "JPEG":
                ext = "jpg"
            elif fmt == "PNG":
                ext = "png"
            elif fmt == "BMP":
                ext = "bmp"
            elif fmt == "TIFF":
                ext = "tif"
            elif fmt=="WEBP":
                ext = "jpg"
            else:
                ext = "jpg"

            # 生成文件名以及存储路径
            strinfo = 'mmbiz_*[a-zA-Z]*/(.*?)\?'
            image_hash_name = re.findall(strinfo, img_url)[0]
            image_path = "wechat_article_img/" + str.format('{0}.{1}', image_hash_name, ext)

            img_data['url'] = img_url
            img_data['img_id'] = img_id
            img_data['article_id'] = article_id
            img_data['path'] = image_path
            img_data['image'] = orig_image
            img_data['img_RAM'] = img_RAM
            results.append(img_data)
        return results

    def img_upload(self,img_data):
        success_imgs = []

        this_id = 0
        for img_data_each in img_data:
            file = StringIO()
            # 将图片存在内存中
            try:
                img_data_each['image'].save(file,"JPEG")
            except Exception as e:
                img_data_each['image'].convert('RGB').save(file,"JPEG")

            # 阿里云身份认证通牒
            auth = oss2.Auth(AliyunAccessKey, AliyunSecretKey)
            upload = oss2.Bucket(auth, AliyunEndPoint, bucketname)
            # 图片上传至阿里云
            upload_result = upload.put_object(img_data_each['path'], file.getvalue())
            # 图片上传成功，进行数据库标记
            if upload_result.status == 200:
                self.db_update(img_data_each)
            # print upload.sign_url('GET', img_data_each['path'], 9999)
            success_imgs.append(img_data_each)
            # 图片下载到本地
            # upload.get_object_to_file(img_data_each['path'], str.format('C:/Users/admin/Desktop/img_test/20180326/{0}.jpg', this_id))
            this_id += 1
            # return "Ash"

    def is_insert(self, article_id, img_id):
        sql_select = """SELECT * from wechat_img_upload where article_id = '%d' and img_id = '%d'""" % (article_id, img_id)
        cursor.execute(sql_select)
        if len(cursor.fetchall()) > 0:
            return True
        else:
            return False

    def db_insert(self, article_id, weixin_name, img_id_insert, img_url):
        sql_insert = """INSERT INTO wechat_img_upload(article_id, weixin_name, img_id, is_upload, img_url) 
            VALUES ('%d', '%s', '%d', '%d', '%s')""" % (article_id, weixin_name, img_id_insert, 0, img_url)
        cursor.execute(sql_insert)
        db.commit()
        print str.format('id = {0} insert OK!', img_id_insert)

    def db_update(self, img_data):
        sql_update = """UPDATE wechat_img_upload set is_upload = 1 where article_id = '%d' and img_id = '%d'""" % (img_data['article_id'], img_data['img_id'])
        cursor.execute(sql_update)
        db.commit()
        print str.format('id = {0} update OK!', img_data['img_id'])

    def update_article(self, article_id):
        sql_update = """UPDATE wechat_text set is_processed = 1 where id = '%d'""" % (article_id)
        cursor.execute(sql_update)
        db.commit()
        print 'article is processed'


if __name__ == '__main__':
    wechat = Wechat_content()
    wechat.engine()







