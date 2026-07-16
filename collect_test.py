# -*- coding: utf-8 -*-
"""快速采集测试 - 采集阿北前3页数据验证完整流程"""
import json
import time
import sys

sys.path.insert(0, 'C:/Users/a/WorkBuddy/2026-07-14-17-37-49/douban-movie-stats')
from douban_spider import DoubanSpider

spider = DoubanSpider('ahbei', delay=1.5)

# 获取前3页列表（45条）
all_records = []
for start in [0, 15, 30]:
    url = (f"https://movie.douban.com/people/ahbei/collect"
           f"?start={start}&sort=time&type=all&filter=all&mode=grid")
    resp = spider._get_with_retry(url)
    if resp:
        records = spider._parse_list_page(resp.text)
        all_records.extend(records)
        print(f"第{start//15+1}页: {len(records)}条", flush=True)
    time.sleep(1.5)

print(f"总计: {len(all_records)}条", flush=True)

# 保存列表
with open(spider.watched_file, 'w', encoding='utf-8') as f:
    json.dump(all_records, f, ensure_ascii=False, indent=2)

# 获取每部详情
cache = spider._load_cache()
for i, r in enumerate(all_records):
    sid = r['subject_id']
    if sid not in cache:
        cache[sid] = spider.fetch_movie_detail(sid, r.get('intro', ''))
        time.sleep(1.5)
    d = cache[sid]
    print(f"  {i+1}/{len(all_records)}: {r['title']} | 导演:{d['directors']} | 类型:{d['types']} | 语言:{d['languages']}", flush=True)
    if (i + 1) % 5 == 0:
        spider._save_cache(cache)

spider._save_cache(cache)
print(f"\n采集完成: {len(cache)}部电影详情", flush=True)
