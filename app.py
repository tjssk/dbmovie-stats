# -*- coding: utf-8 -*-
"""
豆瓣观影记录统计工具 - Web 应用
部署后通过 Railway 提供的域名访问，本地运行默认 http://localhost:5000
"""
import csv
import io
import json
import os
import re
import sys
import threading
import time
from pathlib import Path

import requests

# 确保能找到同目录下的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, request, jsonify, Response

from douban_spider import DoubanSpider
from analyzer import MovieAnalyzer

app = Flask(__name__)

# 采集任务状态（全局）
collect_tasks = {}
# AI 标签分析任务状态（全局）
tag_tasks = {}
# IMDB 评分获取任务状态（全局）
imdb_tasks = {}

# AI 标签候选池（六维标签分析系统，6大板块含子分类）
TAG_CATEGORIES = {
    '情节与前提': {
        '犯罪法律': ['犯罪黑帮', '谋杀悬疑', '追捕卧底', '侦探推理', '绑架抢劫', '诈骗腐败'],
        '动作冒险': ['动作冒险', '生存逃亡', '灾难末世', '战争战斗', '西部牛仔',
            '海盗寻宝', '赛车极限', '武术格斗'],
        '爱情关系': ['爱情浪漫', '家庭', '友情搭档'],
        '奇幻科幻': ['奇幻魔法', '科幻太空', '人工智能', '时间旅行', '超级英雄',
            '变异末日', '赛博朋克'],
        '恐怖超自然': ['恐怖惊悚', '超自然鬼怪'],
        '喜剧成长': ['黑色幽默', '成长救赎', '青春校园', '人生转折'],
    },
    '人物与角色': {
        '职业身份': ['执法人员', '律师法官', '医护人员', '教育工作者', '文艺工作者',
            '科学家', '黑客程序员', '商界人士', '服务业人员', '驾驶员', '军人'],
        '社会角色': ['王室贵族', '孤儿单亲', '兄弟姐妹', '导师门徒', '对手叛徒'],
        '特殊身份': ['天才神童', '疯子狂人', '先知预言家', '时间旅行者', '外星人',
            '机器人克隆人', '变种人', '超自然生物', '神明恶魔'],
    },
    '主要场景': {
        '时空': ['当代', '历史', '未来', '近未来', '维多利亚时代',
            '中世纪', '古代', '20世纪', '战后冷战'],
        '地理': ['城市', '小镇', '乡村', '沙漠丛林', '山脉极地', '海洋岛屿', '太空异世界'],
        '建筑场所': ['豪宅公寓', '学校校园', '办公场所', '机构场所',
            '公共空间', '文化场所', '交通枢纽'],
    },
    '主题与议题': {
        '社会议题': ['阶级贫富', '移民难民', '种族问题', '性别议题', '女性主义',
            'LGBTQ+', '身份认同', '心理健康', '创伤PTSD', '成瘾戒毒',
            '堕胎死刑', '枪支暴力', '校园霸凌'],
        '政治权力': ['政治权力', '腐败独裁', '革命内战', '恐怖主义',
            '压迫自由', '人权正义', '环保气候'],
        '哲学人性': ['存在主义', '宗教信仰', '科技伦理', '记忆身份', '孤独归属',
            '爱与失去', '复仇宽恕', '忠诚背叛', '家庭冲突', '生死议题'],
    },
    '基调与氛围': {
        '情感基调': ['温暖治愈', '感动心碎', '压抑沉重', '阴郁黑暗', '悬疑紧张',
            '惊悚恐怖', '梦幻诗意', '浪漫甜蜜', '幽默诙谐', '轻松舒适'],
        '节奏风格': ['快节奏', '慢节奏', '燃/酣畅', '引人入胜', '荒诞怪诞',
            '极简精致', '粗粝写实', '纪实感', '实验性'],
        '美学感受': ['视觉系', '复古未来感', '田园哥特', '暗黑颓废', '清新温暖', '冷峻冷色调'],
    },
    '形式与结构': {
        '叙事结构': ['线性叙事', '非线性叙事', '倒叙', '多线叙事', '群像',
            '独角戏', '戏中戏', '伪纪录片', '第一人称', '打破第四面墙'],
        '形式类型': ['长片', '短片', '迷你剧', '纪录片', '动画', '默片黑白片',
            '音乐歌舞', '体育电影', '战争历史片', '传记片', '黑色电影'],
        '来源定位': ['改编作品', '原创作品', '续集前传', '重启翻拍',
            '独立电影', '商业大片', '邪典电影'],
        '目标受众': ['合家欢', '青少年向', '成人向'],
    },
}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/health')
def health():
    return jsonify({'status': 'ok'})


@app.route('/api/collect', methods=['POST'])
def start_collect():
    data = request.get_json(force=True)
    uid = (data.get('uid') or '').strip()
    cookie = (data.get('cookie') or '').strip()
    force = bool(data.get('force_refresh', False))

    if not uid:
        return jsonify({'error': '请输入豆瓣 uid'}), 400

    # 检查是否已有任务在运行
    existing = collect_tasks.get(uid)
    if existing and existing.get('status') == 'running':
        return jsonify({'error': '该 uid 的采集任务正在运行中，请等待完成'}), 409

    def run():
        spider = DoubanSpider(uid, cookie, delay=2)
        task = {'status': 'running', 'progress': {
            'phase': 'init', 'message': '正在初始化...'}}

        def progress_cb(p):
            task['progress'] = p

        collect_tasks[uid] = task
        try:
            result = spider.collect_all(progress_cb, force_refresh=force)
            if result:
                task['status'] = 'done'
                task['result'] = {
                    'total': result['total'],
                    'new_count': result['new_count'],
                }
            else:
                task['status'] = 'error'
                task['progress'] = {
                    'phase': 'error',
                    'message': '采集失败——未获取到观影记录。请检查 uid 是否正确，'
                               '或观影记录是否设为私密（需提供登录 Cookie）'
                }
        except Exception as e:
            task['status'] = 'error'
            task['progress'] = {'phase': 'error', 'message': f'采集出错: {e}'}

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return jsonify({'status': 'started', 'uid': uid})


@app.route('/api/collect/status/<uid>')
def collect_status(uid):
    task = collect_tasks.get(uid, {'status': 'idle', 'progress': {}})
    return jsonify(task)


@app.route('/api/stats/<uid>')
def get_stats(uid):
    spider = DoubanSpider(uid)
    data = spider.get_collected_data()
    if not data['watched']:
        return jsonify({'error': '未找到采集数据，请先采集'}), 404

    analyzer = MovieAnalyzer(data['watched'], data['movies'])
    stats = analyzer.analyze()

    # 附加：导演 -> 该导演电影列表（用于悬停显示）
    stats['director_movies'] = _build_director_movies_map(data)

    # 附加：导演性别数据（如果已分析）
    gender_file = spider.data_dir / 'director_genders.json'
    if gender_file.exists():
        with open(gender_file, 'r', encoding='utf-8') as f:
            stats['director_genders'] = json.load(f)
    else:
        stats['director_genders'] = {}

    # 附加一些元信息
    stats['uid'] = uid
    stats['watched_count'] = len(data['watched'])
    stats['cached_count'] = len(data['movies'])
    return jsonify(stats)


def _build_director_movies_map(data):
    """构建 {导演: [电影列表]} 用于图表悬停显示"""
    director_movies = {}
    for r in data['watched']:
        sid = r.get('subject_id', '')
        detail = data['movies'].get(sid, {})
        directors = detail.get('directors', [])
        title = detail.get('title') or r.get('title', '')
        year = detail.get('release_year', '')
        for d in directors:
            director_movies.setdefault(d, []).append({
                'subject_id': sid,
                'title': title,
                'year': year,
                'user_rating': r.get('user_rating', 0),
                'douban_rating': detail.get('douban_rating', ''),
            })
    return director_movies


# ===== AI 工具（导演性别分析） =====

def _call_ai_api(api_url, api_key, model, prompt, timeout=120):
    """调用 OpenAI 兼容的 Chat Completion API"""
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': '你是电影内容分析专家，只输出有效JSON。'},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': 0.3,
    }
    resp = requests.post(api_url, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    content = data['choices'][0]['message']['content'].strip()
    # 去除可能的 markdown 包裹
    if content.startswith('```'):
        content = re.sub(r'^```(?:json)?\s*', '', content)
        content = re.sub(r'\s*```$', '', content)
    return content


# ===== AI 标签分析 =====

def _build_ai_prompt(movies_batch):
    """构建 AI 分析 prompt"""
    lines = []
    for i, m in enumerate(movies_batch, 1):
        types_str = '/'.join(m.get('types', []) or [])
        directors_str = '/'.join(m.get('directors', []) or [])
        lines.append(
            f"{i}. subject_id={m['subject_id']} 标题={m['title']} "
            f"({m.get('release_year', '?')}) 类型={types_str} "
            f"国家={m.get('region', '?')} 导演={directors_str}"
        )
    movies_text = '\n'.join(lines)

    # 按板块和子分类组织标签池
    category_lines = []
    for cat_name, subs in TAG_CATEGORIES.items():
        sub_lines = []
        for sub_name, tags in subs.items():
            sub_lines.append(f"  {sub_name}：{'、'.join(tags)}")
        category_lines.append(f"【{cat_name}】\n" + '\n'.join(sub_lines))
    candidates_text = '\n'.join(category_lines)

    return (
        "你是电影内容分析专家。请分析以下电影列表的六维内容标签——"
        "涵盖情节与前提、人物与角色、主要场景、主题与议题、基调与氛围、形式与结构六大维度。\n\n"
        f"候选标签池（按六大板块分类，请优先从此池选择）：\n{candidates_text}\n\n"
        "每部电影在每个模块选择1-2个最相关的标签，总计返回6-12个标签。\n"
        "请严格按以下JSON数组格式返回（**不要**加任何markdown标记、注释、解释文字）：\n"
        '[{"subject_id":"12345","tags":["标签1","标签2"]},...]'
        "\n\n电影列表：\n" + movies_text
    )


def _parse_ai_tags_response(content):
    """解析 AI 返回的 JSON 数组"""
    try:
        result = json.loads(content)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass
    match = re.search(r'\[.*\]', content, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group(0))
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass
    raise ValueError(f'无法解析 AI 返回内容: {content[:200]}')


@app.route('/api/analyze/tags', methods=['POST'])
def start_tag_analysis():
    """开始 AI 标签分析任务"""
    data = request.get_json(force=True)
    uid = (data.get('uid') or '').strip()
    api_url = (data.get('api_url') or '').strip()
    api_key = (data.get('api_key') or '').strip()
    model = (data.get('model') or 'gpt-4o-mini').strip()
    batch_size = int(data.get('batch_size') or 8)
    force = bool(data.get('force', False))

    if not uid or not api_url or not api_key:
        return jsonify({'error': '缺少必要参数（uid/api_url/api_key）'}), 400

    if batch_size < 1 or batch_size > 30:
        batch_size = 8

    existing = tag_tasks.get(uid)
    if existing and existing.get('status') in ('running', 'paused'):
        return jsonify({'error': '该 uid 的标签分析正在进行中'}), 409

    def run():
        spider = DoubanSpider(uid)
        data_collected = spider.get_collected_data()
        watched = data_collected['watched']
        movies = data_collected['movies']

        if force:
            for sid in movies:
                if 'tags' in movies[sid]:
                    del movies[sid]['tags']
            spider._save_cache(movies)

        pending = []
        for r in watched:
            sid = r.get('subject_id', '')
            detail = movies.get(sid, {})
            if not detail.get('tags'):
                pending.append({
                    'subject_id': sid,
                    'title': detail.get('title') or r.get('title', ''),
                    'release_year': detail.get('release_year', ''),
                    'types': detail.get('types', []),
                    'region': detail.get('region', ''),
                    'directors': detail.get('directors', []),
                })

        task = tag_tasks[uid] = {
            'status': 'running',
            'paused': False,
            'progress': {
                'phase': 'init',
                'current': 0,
                'total': len(pending),
                'message': f'准备分析 {len(pending)} 部电影...',
            },
            'failed_movies': [],
        }

        if not pending:
            task['status'] = 'done'
            task['progress'] = {
                'phase': 'done', 'current': 0, 'total': 0,
                'message': '所有电影已分析过'
            }
            return

        analyzed_count = 0
        error_count = 0
        for batch_start in range(0, len(pending), batch_size):
            while task.get('paused'):
                task['status'] = 'paused'
                task['progress']['message'] = '已暂停'
                time.sleep(1)
            task['status'] = 'running'

            batch = pending[batch_start:batch_start + batch_size]
            task['progress'] = {
                'phase': 'analyzing',
                'current': batch_start,
                'total': len(pending),
                'message': f'正在分析 {batch_start + 1}-{batch_start + len(batch)} / {len(pending)}',
            }
            try:
                prompt = _build_ai_prompt(batch)
                content = _call_ai_api(api_url, api_key, model, prompt)
                results = _parse_ai_tags_response(content)
                for item in results:
                    sid = str(item.get('subject_id', ''))
                    tags = item.get('tags', [])
                    if sid in movies and tags:
                        movies[sid]['tags'] = tags
                        analyzed_count += 1
                spider._save_cache(movies)
                time.sleep(1)
            except Exception as e:
                error_count += 1
                task['failed_movies'].extend([m['subject_id'] for m in batch])
                task['progress']['message'] = f'批次 {batch_start // batch_size + 1} 出错: {str(e)[:100]}'
                time.sleep(2)

        task['status'] = 'done'
        task['progress'] = {
            'phase': 'done',
            'current': len(pending),
            'total': len(pending),
            'message': f'分析完成！共处理 {len(pending)} 部，成功 {analyzed_count} 部'
                      + (f'，失败 {error_count} 批（{len(task["failed_movies"])} 部）' if error_count else ''),
        }

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return jsonify({'status': 'started', 'uid': uid})


@app.route('/api/analyze/tags/status/<uid>')
def tag_analysis_status(uid):
    task = tag_tasks.get(uid, {'status': 'idle', 'progress': {}})
    return jsonify(task)


@app.route('/api/analyze/tags/pause/<uid>', methods=['POST'])
def pause_tag_analysis(uid):
    task = tag_tasks.get(uid)
    if not task:
        return jsonify({'error': '无运行中的任务'}), 404
    task['paused'] = True
    return jsonify({'status': 'ok'})


@app.route('/api/analyze/tags/resume/<uid>', methods=['POST'])
def resume_tag_analysis(uid):
    task = tag_tasks.get(uid)
    if not task:
        return jsonify({'error': '无任务'}), 404
    task['paused'] = False
    return jsonify({'status': 'ok'})


@app.route('/api/analyze/tags/retry/<uid>', methods=['POST'])
def retry_failed_tags(uid):
    """重新分析失败的电影"""
    data = request.get_json(force=True)
    api_url = (data.get('api_url') or '').strip()
    api_key = (data.get('api_key') or '').strip()
    model = (data.get('model') or 'gpt-4o-mini').strip()
    batch_size = int(data.get('batch_size') or 8)

    if not api_url or not api_key:
        return jsonify({'error': '缺少 API 配置'}), 400

    if uid in tag_tasks:
        tag_tasks[uid]['status'] = 'idle'

    return start_tag_analysis()


@app.route('/api/analyze/tags/clear/<uid>', methods=['POST'])
def clear_tags(uid):
    """清除所有 AI 标签"""
    spider = DoubanSpider(uid)
    data = spider.get_collected_data()
    movies = data['movies']
    cleared = 0
    for sid, detail in movies.items():
        if 'tags' in detail:
            del detail['tags']
            cleared += 1
    spider._save_cache(movies)
    return jsonify({'status': 'ok', 'cleared': cleared})


@app.route('/api/analyze/director-genders', methods=['POST'])
def analyze_director_genders():
    """用 AI 分析导演性别"""
    data = request.get_json(force=True)
    uid = (data.get('uid') or '').strip()
    api_url = (data.get('api_url') or '').strip()
    api_key = (data.get('api_key') or '').strip()
    model = (data.get('model') or 'gpt-4o-mini').strip()

    if not uid or not api_url or not api_key:
        return jsonify({'error': '缺少必要参数'}), 400

    spider = DoubanSpider(uid)
    data_collected = spider.get_collected_data()
    movies = data_collected['movies']

    # 收集所有唯一导演名
    directors = set()
    for detail in movies.values():
        for d in detail.get('directors', []):
            directors.add(d)
    directors = sorted(directors)

    if not directors:
        return jsonify({'error': '无导演数据'}), 400

    # 构建提示
    lines = '\n'.join(f'{i+1}. {d}' for i, d in enumerate(directors))
    prompt = (
        '请判断以下电影导演的性别。返回JSON对象，键为导演名，值为 "male" 或 "female" 或 "unknown"。\n'
        '只返回JSON，不要任何其他文字或markdown标记。\n\n'
        f'导演列表：\n{lines}'
    )

    try:
        content = _call_ai_api(api_url, api_key, model, prompt, timeout=60)
        # 去除可能的 markdown 包裹
        if content.startswith('```'):
            content = re.sub(r'^```(?:json)?\s*', '', content)
            content = re.sub(r'\s*```$', '', content)
        # 尝试解析
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                result = json.loads(match.group(0))
            else:
                raise ValueError('无法解析 AI 返回内容')

        # 保存到文件
        gender_file = spider.data_dir / 'director_genders.json'
        with open(gender_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        male_count = sum(1 for v in result.values() if v == 'male')
        female_count = sum(1 for v in result.values() if v == 'female')
        return jsonify({
            'status': 'ok',
            'total': len(directors),
            'male': male_count,
            'female': female_count,
            'unknown': len(directors) - male_count - female_count,
        })
    except Exception as e:
        return jsonify({'error': f'分析失败: {str(e)[:200]}'}), 500


# ===== IMDB 评分获取 =====

@app.route('/api/analyze/imdb-ratings/<uid>', methods=['POST'])
def start_imdb_ratings(uid):
    """开始从 IMDB 官网获取评分"""
    existing = imdb_tasks.get(uid)
    if existing and existing.get('status') == 'running':
        return jsonify({'error': 'IMDB 评分获取正在进行中'}), 409

    def run():
        spider = DoubanSpider(uid)
        task = {'status': 'running', 'progress': {
            'phase': 'init', 'message': '准备获取 IMDB 评分...'}}

        def progress_cb(p):
            task['progress'] = p

        imdb_tasks[uid] = task
        try:
            result = spider.fetch_imdb_ratings(progress_cb)
            task['status'] = 'done'
            task['result'] = result
        except Exception as e:
            task['status'] = 'error'
            task['progress'] = {
                'phase': 'error',
                'message': f'获取 IMDB 评分出错: {e}',
            }

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return jsonify({'status': 'started', 'uid': uid})


@app.route('/api/analyze/imdb-ratings/status/<uid>')
def imdb_ratings_status(uid):
    task = imdb_tasks.get(uid, {'status': 'idle', 'progress': {}})
    return jsonify(task)


@app.route('/api/export/<uid>')
def export_csv(uid):
    """导出 CSV"""
    spider = DoubanSpider(uid)
    data = spider.get_collected_data()
    if not data['watched']:
        return jsonify({'error': '未找到采集数据'}), 404

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        '电影标题', '导演', '演员', '类型', '国家/地区', '语言',
        '上映年份', '片长', '豆瓣评分', 'IMDB评分', '我的评分', '观影日期', '短评', 'AI内容标签'
    ])
    for r in data['watched']:
        detail = data['movies'].get(r.get('subject_id', ''), {})
        user_rating = r.get('user_rating', 0)
        writer.writerow([
            r.get('title', ''),
            ' / '.join(detail.get('directors', [])),
            ' / '.join(detail.get('actors', [])[:5]),
            ' / '.join(detail.get('types', [])),
            detail.get('region', ''),
            ' / '.join(detail.get('languages', [])),
            detail.get('release_year', ''),
            detail.get('duration', ''),
            detail.get('douban_rating', ''),
            detail.get('imdb_rating', ''),
            f"{'★' * user_rating}{'☆' * (5 - user_rating)}" if user_rating > 0 else '',
            r.get('watch_date', ''),
            r.get('comment', ''),
            ' / '.join(detail.get('tags', [])),
        ])

    content = '\ufeff' + output.getvalue()  # BOM for Excel
    return Response(
        content,
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename=douban_{uid}.csv'}
    )


@app.route('/report/<uid>')
def report(uid):
    return render_template('report.html', uid=uid)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("=" * 50)
    print("  豆瓣观影记录统计工具")
    print(f"  服务已启动，监听端口: {port}")
    print("=" * 50)
    app.run(debug=False, host='0.0.0.0', port=port)
