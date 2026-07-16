# -*- coding: utf-8 -*-
"""
豆瓣观影记录采集模块
通过 uid 获取用户"看过"列表，并采集每部电影的详细信息（导演、类型、国家、语言等）
"""
import os
import re
import json
import time
import random
import gzip
import urllib.parse
import requests
from bs4 import BeautifulSoup
from pathlib import Path

BASE_URL = "https://movie.douban.com"

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Referer': 'https://movie.douban.com/',
}

# 豆瓣常见的语言列表，用于从 intro 行中匹配语言
KNOWN_LANGUAGES = {
    # 中文及方言
    '汉语普通话', '粤语', '上海话', '四川话', '东北话', '陕西话', '武汉话',
    '天津话', '南京话', '长沙话', '山东话', '河南话', '闽南语', '客家话',
    '吴语', '湘语', '赣语', '壮语', '藏语', '蒙古语', '维吾尔语', '温州话',
    '苏州话', '宁波话', '青岛话', '唐山话', '山西话', '甘肃话', '合肥话',
    # 亚洲语言
    '日语', '韩语', '朝鲜语', '越南语', '泰语', '缅甸语', '柬埔寨语', '老挝语',
    '马来语', '印尼语', '印度尼西亚语', '他加禄语', '菲律宾语', '印地语',
    '乌尔都语', '孟加拉语', '泰米尔语', '泰卢固语', '旁遮普语', '马拉地语',
    '尼泊尔语', '僧伽罗语', '波斯语', '普什图语', '土耳其语', '阿塞拜疆语',
    '库尔德语', '哈萨克语', '乌兹别克语', '吉尔吉斯语', '塔吉克语',
    '土库曼语', '格鲁吉亚语', '亚美尼亚语',
    # 欧洲语言
    '英语', '法语', '德语', '西班牙语', '意大利语', '葡萄牙语', '俄语',
    '荷兰语', '瑞典语', '芬兰语', '丹麦语', '挪威语', '冰岛语', '波兰语',
    '捷克语', '斯洛伐克语', '匈牙利语', '罗马尼亚语', '保加利亚语',
    '塞尔维亚语', '克罗地亚语', '斯洛文尼亚语', '阿尔巴尼亚语', '希腊语',
    '爱尔兰语', '威尔士语', '加泰罗尼亚语', '巴斯克语', '希伯来语',
    '乌克兰语', '白俄罗斯语', '拉脱维亚语', '立陶宛语', '爱沙尼亚语',
    '马其顿语', '黑山语', '波黑语',
    # 非洲及其他
    '阿拉伯语', '斯瓦希里语', '豪萨语', '阿姆哈拉语', '约鲁巴语', '祖鲁语',
    '阿非利卡语', '毛利语', '夏威夷语', '萨摩亚语', '汤加语', '斐济语',
    '拉丁语', '世界语', '手语', '无对白', '依地语', '吉普赛语', '克林贡语',
}


class DoubanSpider:
    """豆瓣观影记录采集器"""

    def __init__(self, uid, cookie='', delay=2):
        self.uid = uid.strip()
        self.cookie = cookie.strip()
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        if self.cookie:
            self.session.headers['Cookie'] = self.cookie

        # 数据目录
        self.data_dir = Path(__file__).parent / 'data' / self.uid
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.watched_file = self.data_dir / 'watched.json'
        self.cache_file = self.data_dir / 'movies_cache.json'

    def _get_with_retry(self, url, max_retries=3, **kwargs):
        """带重试的 GET 请求"""
        for attempt in range(max_retries):
            try:
                resp = self.session.get(url, timeout=20, **kwargs)
                if resp.status_code == 200:
                    return resp
                elif resp.status_code == 403:
                    # 被封，等待更长时间
                    time.sleep(self.delay * 3)
                else:
                    time.sleep(self.delay)
            except requests.RequestException:
                time.sleep(self.delay)
        return None

    def _load_cache(self):
        """加载电影详情缓存"""
        if self.cache_file.exists():
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _save_cache(self, cache):
        """保存电影详情缓存"""
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)

    def fetch_watched_list(self, progress_callback=None):
        """
        获取用户"看过"列表的所有电影
        返回 list of dict: [{subject_id, title, alt_titles, user_rating, watch_date, comment, intro}, ...]
        """
        all_records = []
        start = 0
        page = 1

        while True:
            url = (f"{BASE_URL}/people/{self.uid}/collect"
                   f"?start={start}&sort=time&type=all&filter=all&mode=grid")
            resp = self._get_with_retry(url)
            if resp is None:
                break

            records = self._parse_list_page(resp.text)
            if not records:
                break

            all_records.extend(records)

            if progress_callback:
                progress_callback({
                    'phase': 'list',
                    'current': len(all_records),
                    'total': None,
                    'message': f'正在获取看过列表... 已获取 {len(all_records)} 部'
                })

            # 检查是否还有下一页
            soup = BeautifulSoup(resp.text, 'lxml')
            next_link = soup.find('a', string=re.compile(r'后页'))
            if not next_link:
                # 也检查分页器中的 next
                next_span = soup.find('span', class_='next')
                if next_span and next_span.find('a'):
                    next_link = next_span.find('a')

            if not next_link:
                break

            start += 15
            page += 1
            time.sleep(self.delay + random.uniform(0, 1))

        # 保存观影记录
        with open(self.watched_file, 'w', encoding='utf-8') as f:
            json.dump(all_records, f, ensure_ascii=False, indent=2)

        return all_records

    def _parse_list_page(self, html):
        """解析列表页，提取观影记录"""
        soup = BeautifulSoup(html, 'lxml')
        items = soup.select('.grid-view .item')
        if not items:
            items = soup.select('.item.comment-item')
        if not items:
            # 兜底：找所有包含 subject 链接的 item div
            items = soup.find_all('div', class_=re.compile(r'\bitem\b'))

        records = []
        for item in items:
            record = self._parse_list_item(item)
            if record and record['subject_id']:
                records.append(record)
        return records

    def _parse_list_item(self, item):
        """解析单条观影记录"""
        record = {
            'subject_id': '',
            'title': '',
            'alt_titles': '',
            'user_rating': 0,
            'watch_date': '',
            'comment': '',
            'intro': '',
        }

        # 提取电影链接和标题
        title_li = item.find('li', class_='title')
        if title_li:
            link = title_li.find('a')
            if link:
                href = link.get('href', '')
                match = re.search(r'subject/(\d+)', href)
                if match:
                    record['subject_id'] = match.group(1)
                # 标题在 <em> 中，别名在 <a> 文本中
                em = link.find('em')
                if em:
                    record['title'] = em.get_text(strip=True)
                full_text = link.get_text(strip=True)
                if record['title'] and full_text.startswith(record['title']):
                    record['alt_titles'] = full_text[len(record['title']):].strip(' /')

        # 兜底：从 pic 区域的链接提取
        if not record['subject_id']:
            pic = item.find('div', class_='pic')
            if pic:
                link = pic.find('a')
                if link:
                    href = link.get('href', '')
                    match = re.search(r'subject/(\d+)', href)
                    if match:
                        record['subject_id'] = match.group(1)
                    if not record['title']:
                        record['title'] = link.get('title', '') or link.get_text(strip=True)

        if not record['subject_id']:
            return None

        # 提取 intro 行（包含混合信息）
        intro_li = item.find('li', class_='intro')
        if intro_li:
            record['intro'] = intro_li.get_text(strip=True)

        # 提取评分（rating1-t ~ rating5-t）
        rating_span = item.find('span', class_=re.compile(r'rating\d-t'))
        if rating_span:
            classes = rating_span.get('class', [])
            for cls in classes:
                m = re.match(r'rating(\d)-t', cls)
                if m:
                    record['user_rating'] = int(m.group(1))
                    break

        # 提取观影日期
        date_span = item.find('span', class_='date')
        if date_span:
            record['watch_date'] = date_span.get_text(strip=True)

        # 提取短评
        comment_span = item.find('span', class_='comment')
        if comment_span:
            record['comment'] = comment_span.get_text(strip=True)

        return record

    def fetch_movie_detail(self, subject_id, intro=''):
        """
        获取单部电影详情
        优先使用 subject_abstract API，从 intro 行补充语言信息
        """
        detail = {
            'subject_id': subject_id,
            'title': '',
            'directors': [],
            'types': [],
            'region': '',
            'release_year': '',
            'duration': '',
            'douban_rating': '',
            'imdb_rating': '',
            'actors': [],
            'languages': [],
        }

        # 调用 API
        api_url = f"{BASE_URL}/j/subject_abstract?subject_id={subject_id}"
        resp = self._get_with_retry(api_url)
        if resp:
            try:
                data = resp.json()
                if data.get('r') == 0 and data.get('subject'):
                    s = data['subject']
                    detail['title'] = s.get('title', '')
                    detail['directors'] = s.get('directors', [])
                    detail['types'] = s.get('types', [])
                    detail['region'] = s.get('region', '')
                    detail['release_year'] = str(s.get('release_year', ''))
                    detail['duration'] = s.get('duration', '')
                    detail['douban_rating'] = str(s.get('rate', ''))
                    detail['imdb_rating'] = str(s.get('imdb_rating', ''))
                    detail['actors'] = s.get('actors', [])[:10]  # 只取前10位
            except (json.JSONDecodeError, KeyError):
                pass

        # 从 intro 行提取语言
        if intro:
            detail['languages'] = self._extract_languages(intro)

        return detail

    def _extract_languages(self, intro):
        """从 intro 行中提取语言"""
        if not intro:
            return []
        items = [item.strip() for item in intro.split(' / ')]
        languages = []
        for item in items:
            if item in KNOWN_LANGUAGES:
                languages.append(item)
        return languages

    def collect_all(self, progress_callback=None, force_refresh=False):
        """
        采集完整数据：列表 + 每部电影详情
        progress_callback: 回调函数，接收进度 dict
        force_refresh: 是否强制刷新缓存
        """
        # 第一步：获取看过列表
        if progress_callback:
            progress_callback({
                'phase': 'list',
                'current': 0,
                'total': None,
                'message': '开始获取看过列表...'
            })

        watched = self.fetch_watched_list(progress_callback)
        if not watched:
            if progress_callback:
                progress_callback({
                    'phase': 'error',
                    'message': '未获取到任何观影记录，请检查 uid 是否正确，或观影记录是否为私密（需提供 Cookie）'
                })
            return None

        # 第二步：获取每部电影详情
        cache = {} if force_refresh else self._load_cache()
        total = len(watched)
        new_count = 0
        error_count = 0

        for i, record in enumerate(watched):
            sid = record['subject_id']

            if progress_callback:
                msg = f'正在采集电影详情... {i + 1}/{total}'
                if sid in cache:
                    msg += f'（缓存）'
                progress_callback({
                    'phase': 'detail',
                    'current': i + 1,
                    'total': total,
                    'message': msg
                })

            if sid not in cache or force_refresh:
                detail = self.fetch_movie_detail(sid, record.get('intro', ''))
                cache[sid] = detail
                new_count += 1
                # 定期保存缓存
                if new_count % 5 == 0:
                    self._save_cache(cache)
                # 请求间隔
                time.sleep(self.delay + random.uniform(0, 1))
            # 已缓存的直接跳过，不等待

        # 保存缓存
        self._save_cache(cache)

        if progress_callback:
            progress_callback({
                'phase': 'done',
                'current': total,
                'total': total,
                'message': f'采集完成！共 {total} 部电影，本次新采集 {new_count} 部'
            })

        return {
            'watched': watched,
            'movies': cache,
            'total': total,
            'new_count': new_count,
        }

    def get_collected_data(self):
        """获取已采集的数据（不重新采集）"""
        watched = []
        movies = {}
        if self.watched_file.exists():
            with open(self.watched_file, 'r', encoding='utf-8') as f:
                watched = json.load(f)
        if self.cache_file.exists():
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                movies = json.load(f)
        return {'watched': watched, 'movies': movies}

    # ===== IMDB 评分获取 =====

    IMDB_RATINGS_URL = 'https://datasets.imdbws.com/title.ratings.tsv.gz'
    IMDB_SUGGESTION_API = 'https://v3.sg.media-imdb.com/suggestion/h/{letter}/{title}.json'

    def _download_imdb_ratings(self):
        """下载 IMDB 官方评分数据集，返回 {imdb_id: rating_str} 字典"""
        resp = requests.get(self.IMDB_RATINGS_URL,
                            headers={'User-Agent': 'Mozilla/5.0'},
                            timeout=60, stream=True)
        if resp.status_code != 200:
            raise RuntimeError(f'下载 IMDB 数据集失败: HTTP {resp.status_code}')

        # 解压并解析 TSV
        ratings = {}
        with gzip.GzipFile(fileobj=resp.raw) as f:
            header = f.readline().decode('utf-8').strip().split('\t')
            id_idx = header.index('tconst')
            rate_idx = header.index('averageRating')
            for line in f:
                parts = line.decode('utf-8').strip().split('\t')
                if len(parts) > rate_idx:
                    ratings[parts[id_idx]] = parts[rate_idx]
        return ratings

    def _search_imdb_id(self, title, year=''):
        """通过 IMDB suggestion API 搜索电影的 IMDB ID"""
        if not title:
            return ''

        # 清理标题中的年份
        clean = re.sub(r'\s*[(\uff08]\d{4}[)\uff09]\s*$', '', title).strip()
        if not clean:
            return ''

        first_letter = clean[0].lower()
        encoded = urllib.parse.quote(clean)
        url = self.IMDB_SUGGESTION_API.format(letter=first_letter, title=encoded)

        try:
            resp = requests.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'Accept': 'application/json',
            }, timeout=10)
            if resp.status_code != 200:
                return ''
            results = resp.json().get('d', [])
        except (requests.RequestException, json.JSONDecodeError):
            return ''

        if not results:
            return ''

        # 按年份过滤
        if year:
            try:
                year_int = int(year)
                year_matches = [r for r in results if r.get('y') == year_int]
                if year_matches:
                    results = year_matches
            except ValueError:
                pass

        # 优先选择电影类型
        movie_types = ('feature', 'TV movie', 'video', 'short')
        movie_results = [r for r in results if r.get('q') in movie_types]
        if movie_results:
            results = movie_results

        return results[0].get('id', '')

    def fetch_imdb_ratings(self, progress_callback=None):
        """批量获取所有电影的 IMDB 评分
        1. 下载 IMDB 官方评分数据集
        2. 对每部电影通过 suggestion API 获取 IMDB ID
        3. 从数据集中查表获取评分
        """
        movies = self._load_cache()
        if not movies:
            return {'total': 0, 'found': 0, 'failed': 0}

        total = len(movies)

        # 第一步：下载评分数据集
        if progress_callback:
            progress_callback({
                'phase': 'download',
                'current': 0, 'total': total,
                'message': '正在下载 IMDB 官方评分数据集（约 8MB）...',
            })

        try:
            ratings_db = self._download_imdb_ratings()
        except Exception as e:
            if progress_callback:
                progress_callback({
                    'phase': 'error',
                    'message': f'下载 IMDB 数据集失败: {e}',
                })
            return {'total': total, 'found': 0, 'failed': total, 'error': str(e)}

        # 第二步：逐部电影搜索 IMDB ID 并查表
        found = 0
        failed = 0
        processed = 0

        for sid, detail in movies.items():
            processed += 1
            title = detail.get('title', '')
            year = detail.get('release_year', '')

            # 跳过已有 IMDB 评分的
            existing = detail.get('imdb_rating', '')
            if existing and existing not in ('', 'None', '0', '0.0'):
                found += 1
                continue

            if progress_callback and processed % 10 == 0:
                progress_callback({
                    'phase': 'searching',
                    'current': processed, 'total': total,
                    'message': f'正在搜索 IMDB 评分... {processed}/{total}（已找到 {found}）',
                })

            imdb_id = self._search_imdb_id(title, year)
            if imdb_id and imdb_id in ratings_db:
                detail['imdb_rating'] = ratings_db[imdb_id]
                found += 1
            else:
                failed += 1

            # 每 20 部保存一次
            if processed % 20 == 0:
                self._save_cache(movies)

            # 请求间隔（suggestion API 限制较松，但仍需控制频率）
            time.sleep(0.3)

        # 最终保存
        self._save_cache(movies)

        if progress_callback:
            progress_callback({
                'phase': 'done',
                'current': total, 'total': total,
                'message': f'IMDB 评分获取完成！共 {total} 部，找到 {found} 部，未找到 {failed} 部',
            })

        return {'total': total, 'found': found, 'failed': failed}


if __name__ == '__main__':
    # 测试：用阿北的公开数据测试
    spider = DoubanSpider('ahbei', delay=2)

    # 只测试列表页解析
    print("测试列表页解析...")
    url = f"{BASE_URL}/people/ahbei/collect?start=0&sort=time&type=all&filter=all&mode=grid"
    resp = spider._get_with_retry(url)
    if resp:
        records = spider._parse_list_page(resp.text)
        print(f"解析到 {len(records)} 条记录")
        for r in records[:3]:
            print(f"\n--- {r['title']} ---")
            print(f"  subject_id: {r['subject_id']}")
            print(f"  user_rating: {r['user_rating']}")
            print(f"  watch_date: {r['watch_date']}")
            print(f"  comment: {r['comment']}")
            print(f"  intro: {r['intro'][:80]}...")

        # 测试详情获取
        print("\n\n测试详情获取...")
        if records:
            detail = spider.fetch_movie_detail(
                records[0]['subject_id'], records[0].get('intro', ''))
            print(f"\n电影: {detail['title']}")
            print(f"  导演: {detail['directors']}")
            print(f"  类型: {detail['types']}")
            print(f"  国家: {detail['region']}")
            print(f"  年份: {detail['release_year']}")
            print(f"  片长: {detail['duration']}")
            print(f"  豆瓣评分: {detail['douban_rating']}")
            print(f"  语言: {detail['languages']}")
