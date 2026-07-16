# -*- coding: utf-8 -*-
"""
观影数据统计分析模块
统计导演、类型、国家、语言、上映年份等维度的分布
"""
from collections import Counter
from datetime import datetime


# ===== AI 内容标签六维系统（6大模块、子分类、颜色） =====
TAG_CATEGORIES = {
    'plot': {
        'name': '情节与前提',
        'sub_categories': [
            {'name': '犯罪法律', 'color': '#B58F8F', 'tags': [
                '犯罪黑帮', '谋杀悬疑', '追捕卧底', '侦探推理', '绑架抢劫', '诈骗腐败',
            ]},
            {'name': '动作冒险', 'color': '#CBABB2', 'tags': [
                '动作冒险', '生存逃亡', '灾难末世', '战争战斗', '西部牛仔',
                '海盗寻宝', '赛车极限', '武术格斗',
            ]},
            {'name': '爱情关系', 'color': '#B68A98', 'tags': [
                '爱情浪漫', '家庭', '友情搭档',
            ]},
            {'name': '奇幻科幻', 'color': '#A47E90', 'tags': [
                '奇幻魔法', '科幻太空', '人工智能', '时间旅行',
                '超级英雄', '变异末日', '赛博朋克',
            ]},
            {'name': '恐怖超自然', 'color': '#835B5B', 'tags': [
                '恐怖惊悚', '超自然鬼怪',
            ]},
            {'name': '喜剧成长', 'color': '#C5AE9F', 'tags': [
                '黑色幽默', '成长救赎', '青春校园', '人生转折',
            ]},
        ],
    },
    'characters': {
        'name': '人物与角色',
        'sub_categories': [
            {'name': '职业身份', 'color': '#AF9871', 'tags': [
                '执法人员', '律师法官', '医护人员', '教育工作者', '文艺工作者',
                '科学家', '黑客程序员', '商界人士', '服务业人员', '驾驶员', '军人',
            ]},
            {'name': '社会角色', 'color': '#978454', 'tags': [
                '王室贵族', '孤儿单亲', '兄弟姐妹', '导师门徒', '对手叛徒',
            ]},
            {'name': '特殊身份', 'color': '#85744F', 'tags': [
                '天才神童', '疯子狂人', '先知预言家', '时间旅行者', '外星人',
                '机器人克隆人', '变种人', '超自然生物', '神明恶魔',
            ]},
        ],
    },
    'scenes': {
        'name': '主要场景',
        'sub_categories': [
            {'name': '时空', 'color': '#839887', 'tags': [
                '当代', '历史', '未来', '近未来', '维多利亚时代',
                '中世纪', '古代', '20世纪', '战后冷战',
            ]},
            {'name': '地理', 'color': '#647C6D', 'tags': [
                '城市', '小镇', '乡村', '沙漠丛林', '山脉极地',
                '海洋岛屿', '太空异世界',
            ]},
            {'name': '建筑场所', 'color': '#768267', 'tags': [
                '豪宅公寓', '学校校园', '办公场所', '机构场所',
                '公共空间', '文化场所', '交通枢纽',
            ]},
        ],
    },
    'themes': {
        'name': '主题与议题',
        'sub_categories': [
            {'name': '社会议题', 'color': '#8399AD', 'tags': [
                '阶级贫富', '移民难民', '种族问题', '性别议题', '女性主义',
                'LGBTQ+', '身份认同', '心理健康', '创伤PTSD', '成瘾戒毒',
                '堕胎死刑', '枪支暴力', '校园霸凌',
            ]},
            {'name': '政治权力', 'color': '#5F7389', 'tags': [
                '政治权力', '腐败独裁', '革命内战', '恐怖主义',
                '压迫自由', '人权正义', '环保气候',
            ]},
            {'name': '哲学人性', 'color': '#626D86', 'tags': [
                '存在主义', '宗教信仰', '科技伦理', '记忆身份', '孤独归属',
                '爱与失去', '复仇宽恕', '忠诚背叛', '家庭冲突', '生死议题',
            ]},
        ],
    },
    'tone': {
        'name': '基调与氛围',
        'sub_categories': [
            {'name': '情感基调', 'color': '#A596B0', 'tags': [
                '温暖治愈', '感动心碎', '压抑沉重', '阴郁黑暗', '悬疑紧张',
                '惊悚恐怖', '梦幻诗意', '浪漫甜蜜', '幽默诙谐', '轻松舒适',
            ]},
            {'name': '节奏风格', 'color': '#857A96', 'tags': [
                '快节奏', '慢节奏', '燃/酣畅', '引人入胜', '荒诞怪诞',
                '极简精致', '粗粝写实', '纪实感', '实验性',
            ]},
            {'name': '美学感受', 'color': '#8B7296', 'tags': [
                '视觉系', '复古未来感', '田园哥特', '暗黑颓废', '清新温暖', '冷峻冷色调',
            ]},
        ],
    },
    'form': {
        'name': '形式与结构',
        'sub_categories': [
            {'name': '叙事结构', 'color': '#60888A', 'tags': [
                '线性叙事', '非线性叙事', '倒叙', '多线叙事', '群像',
                '独角戏', '戏中戏', '伪纪录片', '第一人称', '打破第四面墙',
            ]},
            {'name': '形式类型', 'color': '#4E706D', 'tags': [
                '长片', '短片', '迷你剧', '纪录片', '动画', '默片黑白片',
                '音乐歌舞', '体育电影', '战争历史片', '传记片', '黑色电影',
            ]},
            {'name': '来源定位', 'color': '#5E8086', 'tags': [
                '改编作品', '原创作品', '续集前传', '重启翻拍',
                '独立电影', '商业大片', '邪典电影',
            ]},
            {'name': '目标受众', 'color': '#6C948B', 'tags': [
                '合家欢', '青少年向', '成人向',
            ]},
        ],
    },
}

# 反向索引：tag -> (category_key, color, sub_category_name)
# 首次出现优先，处理跨子分类重复标签
_TAG_TO_CATEGORY = {}
_TAG_TO_COLOR = {}
_TAG_TO_SUB = {}
for _key, _info in TAG_CATEGORIES.items():
    for _sub in _info['sub_categories']:
        for _tag in _sub['tags']:
            if _tag not in _TAG_TO_CATEGORY:
                _TAG_TO_CATEGORY[_tag] = _key
                _TAG_TO_COLOR[_tag] = _sub['color']
                _TAG_TO_SUB[_tag] = _sub['name']


class MovieAnalyzer:
    """观影数据统计分析器"""

    def __init__(self, watched, movies):
        """
        watched: list of dict, 观影记录
        movies: dict, {subject_id: detail_dict}
        """
        self.watched = watched or []
        self.movies = movies or {}

    def _split_field(self, value):
        """分割可能包含多个值的字段（如 '美国 / 英国'）"""
        if not value:
            return []
        parts = [v.strip() for v in str(value).split('/')]
        return [p for p in parts if p]

    def analyze(self):
        """执行全部分析，返回统计结果 dict"""
        return {
            'overview': self._analyze_overview(),
            'directors': self._analyze_directors(),
            'director_ratings': self._analyze_director_ratings(),
            'types': self._analyze_types(),
            'regions': self._analyze_regions(),
            'languages': self._analyze_languages(),
            'release_years': self._analyze_release_years(),
            'user_ratings': self._analyze_user_ratings(),
            'douban_ratings': self._analyze_douban_ratings(),
            'watch_years': self._analyze_watch_years(),
            'watch_timeline': self._analyze_watch_timeline(),
            'decades': self._analyze_decades(),
            'tag_clouds': self._analyze_tag_clouds(),
            'tags_count': self._analyze_tags_count(),
            'movies_full': self._analyze_movies_full(),
        }

    def _analyze_overview(self):
        """概览统计"""
        total = len(self.watched)

        # 评分过的数量
        rated = [r for r in self.watched if r.get('user_rating', 0) > 0]
        avg_user_rating = (
            sum(r['user_rating'] for r in rated) / len(rated)
            if rated else 0
        )

        # 豆瓣平均分
        douban_scores = []
        for r in self.watched:
            detail = self.movies.get(r.get('subject_id', ''), {})
            score = detail.get('douban_rating', '')
            if score:
                try:
                    douban_scores.append(float(score))
                except ValueError:
                    pass
        avg_douban_rating = (
            sum(douban_scores) / len(douban_scores)
            if douban_scores else 0
        )

        # 有短评的数量
        commented = [r for r in self.watched if r.get('comment', '')]

        # 最爱导演
        directors_counter = Counter()
        for r in self.watched:
            detail = self.movies.get(r.get('subject_id', ''), {})
            for d in detail.get('directors', []):
                directors_counter[d] += 1
        top_director = directors_counter.most_common(1)[0] if directors_counter else ('-', 0)

        # 最爱类型
        types_counter = Counter()
        for r in self.watched:
            detail = self.movies.get(r.get('subject_id', ''), {})
            for t in detail.get('types', []):
                types_counter[t] += 1
        top_type = types_counter.most_common(1)[0] if types_counter else ('-', 0)

        # 最爱国家
        regions_counter = Counter()
        for r in self.watched:
            detail = self.movies.get(r.get('subject_id', ''), {})
            for reg in self._split_field(detail.get('region', '')):
                regions_counter[reg] += 1
        top_region = regions_counter.most_common(1)[0] if regions_counter else ('-', 0)

        # 观影时间跨度
        dates = [r.get('watch_date', '') for r in self.watched if r.get('watch_date', '')]
        dates.sort()
        first_date = dates[0] if dates else '-'
        last_date = dates[-1] if dates else '-'

        return {
            'total_movies': total,
            'total_rated': len(rated),
            'avg_user_rating': round(avg_user_rating, 2),
            'avg_douban_rating': round(avg_douban_rating, 2),
            'total_commented': len(commented),
            'top_director': top_director[0],
            'top_director_count': top_director[1],
            'top_type': top_type[0],
            'top_type_count': top_type[1],
            'top_region': top_region[0],
            'top_region_count': top_region[1],
            'first_watch_date': first_date,
            'last_watch_date': last_date,
            'unique_directors': len(directors_counter),
            'unique_types': len(types_counter),
            'unique_regions': len(regions_counter),
        }

    def _analyze_directors(self):
        """导演出现次数 Top N"""
        counter = Counter()
        for r in self.watched:
            detail = self.movies.get(r.get('subject_id', ''), {})
            for d in detail.get('directors', []):
                counter[d] += 1
        return [{'name': name, 'count': count}
                for name, count in counter.most_common(30)]

    def _analyze_director_ratings(self):
        """导演评分对比：用户给该导演作品的平均分 vs 豆瓣平台该导演作品的平均分
        仅统计用户看过 ≥3 部的导演，按观影数降序取 Top 15
        用户评分 1-5 星换算为 10 分制 (×2) 以便与豆瓣评分对比
        """
        director_movies = {}  # {director: [{user_rating, douban_rating}, ...]}
        for r in self.watched:
            detail = self.movies.get(r.get('subject_id', ''), {})
            for d in detail.get('directors', []):
                if d not in director_movies:
                    director_movies[d] = []
                user_r = r.get('user_rating', 0)
                douban_r = detail.get('douban_rating', '')
                douban_val = 0.0
                if douban_r:
                    try:
                        douban_val = float(douban_r)
                    except ValueError:
                        pass
                director_movies[d].append({
                    'user_rating': user_r,
                    'douban_rating': douban_val,
                })

        results = []
        for director, movies in director_movies.items():
            if len(movies) < 3:
                continue
            # 用户平均分（换算10分制）
            rated = [m['user_rating'] for m in movies if m['user_rating'] > 0]
            avg_user = (sum(rated) / len(rated) * 2) if rated else 0  # 5星→10分
            # 豆瓣平均分
            douban_scores = [m['douban_rating'] for m in movies if m['douban_rating'] > 0]
            avg_douban = (sum(douban_scores) / len(douban_scores)) if douban_scores else 0
            # 评分差（用户 vs 豆瓣）
            diff = round(avg_user - avg_douban, 2) if avg_user > 0 and avg_douban > 0 else None

            results.append({
                'name': director,
                'count': len(movies),
                'avg_user_rating': round(avg_user, 2),
                'avg_douban_rating': round(avg_douban, 2),
                'rating_diff': diff,
            })

        # 按观影数降序，取 Top 15
        results.sort(key=lambda x: x['count'], reverse=True)
        return results[:15]

    def _analyze_types(self):
        """影片类型分布"""
        counter = Counter()
        for r in self.watched:
            detail = self.movies.get(r.get('subject_id', ''), {})
            for t in detail.get('types', []):
                counter[t] += 1
        return [{'name': name, 'count': count}
                for name, count in counter.most_common()]

    def _analyze_regions(self):
        """制片国家/地区分布"""
        counter = Counter()
        for r in self.watched:
            detail = self.movies.get(r.get('subject_id', ''), {})
            for reg in self._split_field(detail.get('region', '')):
                counter[reg] += 1
        return [{'name': name, 'count': count}
                for name, count in counter.most_common(20)]

    def _analyze_languages(self):
        """语言分布"""
        counter = Counter()
        for r in self.watched:
            detail = self.movies.get(r.get('subject_id', ''), {})
            for lang in detail.get('languages', []):
                counter[lang] += 1
        return [{'name': name, 'count': count}
                for name, count in counter.most_common(20)]

    def _analyze_release_years(self):
        """上映年份分布"""
        counter = Counter()
        for r in self.watched:
            detail = self.movies.get(r.get('subject_id', ''), {})
            year = detail.get('release_year', '')
            if year and year != 'None':
                counter[year] += 1
        # 按年份排序
        sorted_items = sorted(counter.items(), key=lambda x: x[0])
        return [{'name': y, 'count': c} for y, c in sorted_items]

    def _analyze_decades(self):
        """年代分布（如 1990s, 2000s, 2010s, 2020s）"""
        counter = Counter()
        for r in self.watched:
            detail = self.movies.get(r.get('subject_id', ''), {})
            year = detail.get('release_year', '')
            if year and year != 'None':
                try:
                    decade = (int(year) // 10) * 10
                    counter[f"{decade}s"] += 1
                except ValueError:
                    pass
        sorted_items = sorted(counter.items(), key=lambda x: x[0])
        return [{'name': d, 'count': c} for d, c in sorted_items]

    def _analyze_user_ratings(self):
        """用户评分分布（1-5星）"""
        counter = Counter()
        for r in self.watched:
            rating = r.get('user_rating', 0)
            if rating > 0:
                counter[f"{rating}星"] += 1
        # 确保顺序 1星~5星
        order = ['1星', '2星', '3星', '4星', '5星']
        return [{'name': star, 'count': counter.get(star, 0)} for star in order]

    def _analyze_douban_ratings(self):
        """豆瓣评分区间分布"""
        ranges = [
            ('≤5.0', 0, 5.0),
            ('5.1-6.0', 5.1, 6.0),
            ('6.1-7.0', 6.1, 7.0),
            ('7.1-8.0', 7.1, 8.0),
            ('8.1-9.0', 8.1, 9.0),
            ('9.1-10.0', 9.1, 10.0),
        ]
        counts = {label: 0 for label, _, _ in ranges}
        for r in self.watched:
            detail = self.movies.get(r.get('subject_id', ''), {})
            score = detail.get('douban_rating', '')
            if score:
                try:
                    s = float(score)
                    for label, low, high in ranges:
                        if low <= s <= high:
                            counts[label] += 1
                            break
                except ValueError:
                    pass
        return [{'name': label, 'count': counts[label]} for label, _, _ in ranges]

    def _analyze_watch_years(self):
        """观影年份分布"""
        counter = Counter()
        for r in self.watched:
            date = r.get('watch_date', '')
            if date and len(date) >= 4:
                counter[date[:4]] += 1
        sorted_items = sorted(counter.items(), key=lambda x: x[0])
        return [{'name': y, 'count': c} for y, c in sorted_items]

    def _analyze_watch_timeline(self):
        """观影时间线（按年-月）"""
        counter = Counter()
        for r in self.watched:
            date = r.get('watch_date', '')
            if date and len(date) >= 7:
                counter[date[:7]] += 1
        sorted_items = sorted(counter.items(), key=lambda x: x[0])
        return [{'name': m, 'count': c} for m, c in sorted_items]

    def _analyze_tag_clouds(self):
        """AI 内容标签词云数据（合并为单个词云，按维度子分类着色）
        返回:
          - tags: 扁平列表 [{name, value, color, category, sub_category, movies}]
          - legend: 六大维度的图例数据
        """
        tag_data = {}  # tag -> {value, color, category, sub_category, movies}

        for record in self.watched:
            sid = record.get('subject_id', '')
            detail = self.movies.get(sid, {})
            for tag in detail.get('tags', []):
                if not tag:
                    continue
                color = _TAG_TO_COLOR.get(tag, '#999999')
                cat_key = _TAG_TO_CATEGORY.get(tag, 'other')
                cat_name = TAG_CATEGORIES.get(cat_key, {}).get('name', '其他')
                sub_name = _TAG_TO_SUB.get(tag, '')

                if tag not in tag_data:
                    tag_data[tag] = {
                        'name': tag,
                        'value': 0,
                        'color': color,
                        'category': cat_name,
                        'sub_category': sub_name,
                        'movies': [],
                    }
                tag_data[tag]['value'] += 1
                tag_data[tag]['movies'].append({
                    'subject_id': sid,
                    'title': detail.get('title') or record.get('title', ''),
                    'year': detail.get('release_year', ''),
                    'douban_rating': detail.get('douban_rating', ''),
                })

        # 按出现次数降序
        tags_list = sorted(tag_data.values(), key=lambda x: x['value'], reverse=True)

        # 构建图例
        legend = []
        for key, info in TAG_CATEGORIES.items():
            sub_list = [{'name': s['name'], 'color': s['color']}
                        for s in info['sub_categories']]
            legend.append({'name': info['name'], 'subs': sub_list})

        return {
            'tags': tags_list,
            'legend': legend,
        }

    def _analyze_tags_count(self):
        """已分析标签的电影数量 / 总数"""
        total_movies = len(self.watched)
        analyzed = 0
        for r in self.watched:
            sid = r.get('subject_id', '')
            detail = self.movies.get(sid, {})
            if detail.get('tags'):
                analyzed += 1
        return {
            'analyzed': analyzed,
            'total': total_movies,
            'unanalyzed': total_movies - analyzed,
        }

    def _analyze_movies_full(self):
        """完整影片列表（供筛选用）
        每条记录包含所有可筛选字段
        """
        result = []
        for r in self.watched:
            sid = r.get('subject_id', '')
            detail = self.movies.get(sid, {})
            result.append({
                'subject_id': sid,
                'title': detail.get('title') or r.get('title', ''),
                'alt_titles': r.get('alt_titles', ''),
                'comment': r.get('comment', ''),
                'directors': detail.get('directors', []),
                'actors': detail.get('actors', []),
                'types': detail.get('types', []),
                'region': detail.get('region', ''),
                'languages': detail.get('languages', []),
                'release_year': detail.get('release_year', ''),
                'duration': detail.get('duration', ''),
                'douban_rating': detail.get('douban_rating', ''),
                'imdb_rating': detail.get('imdb_rating', ''),
                'user_rating': r.get('user_rating', 0),
                'watch_date': r.get('watch_date', ''),
                'tags': detail.get('tags', []),
            })
        # 按观影日期降序
        result.sort(key=lambda x: x.get('watch_date', ''), reverse=True)
        return result


if __name__ == '__main__':
    # 测试：用已采集的阿北数据
    import json
    from pathlib import Path

    data_dir = Path(__file__).parent / 'data' / 'ahbei'
    watched_file = data_dir / 'watched.json'
    cache_file = data_dir / 'movies_cache.json'

    if watched_file.exists() and cache_file.exists():
        with open(watched_file, 'r', encoding='utf-8') as f:
            watched = json.load(f)
        with open(cache_file, 'r', encoding='utf-8') as f:
            movies = json.load(f)

        analyzer = MovieAnalyzer(watched, movies)
        stats = analyzer.analyze()

        print("=== 概览 ===")
        for k, v in stats['overview'].items():
            print(f"  {k}: {v}")

        print(f"\n=== 导演 Top 5 ===")
        for d in stats['directors'][:5]:
            print(f"  {d['name']}: {d['count']}")

        print(f"\n=== 类型分布 ===")
        for t in stats['types'][:10]:
            print(f"  {t['name']}: {t['count']}")

        print(f"\n=== 国家/地区 Top 5 ===")
        for r in stats['regions'][:5]:
            print(f"  {r['name']}: {r['count']}")

        print(f"\n=== 语言 Top 5 ===")
        for l in stats['languages'][:5]:
            print(f"  {l['name']}: {l['count']}")
    else:
        print("请先运行 spider 采集数据")
