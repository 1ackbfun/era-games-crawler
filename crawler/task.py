import os
import platform
import json
import pendulum
import requests
from bs4 import BeautifulSoup
import lxml


class Utils:

    @staticmethod
    def jst_to_cst(jst_str: str) -> str:
        jst_str = jst_str.replace('㈪', ' Monday')
        jst_str = jst_str.replace('㈫', ' Tuesday')
        jst_str = jst_str.replace('㈬', ' Wednesday')
        jst_str = jst_str.replace('㈭', ' Thursday')
        jst_str = jst_str.replace('㈮', ' Friday')
        jst_str = jst_str.replace('㈯', ' Saturday')
        jst_str = jst_str.replace('㈰', ' Sunday')
        jst_time = pendulum.from_format(
            jst_str, 'YY/MM/DD dddd HH:mm:ss', tz='Asia/Tokyo')
        cst_time = jst_time.in_timezone('Asia/Shanghai')
        return cst_time.format('YYYY-MM-DD HH:mm:ss')

    @staticmethod
    def get_timestamp(time_str: str) -> int:
        cst_time = pendulum.from_format(
            time_str, 'YYYY-MM-DD HH:mm:ss', tz='Asia/Shanghai')
        return cst_time.int_timestamp

    @staticmethod
    def now(is_timestamp: bool = False) -> tuple[str, int]:
        current = pendulum.now('Asia/Shanghai')
        if is_timestamp:
            return current.int_timestamp
        else:
            return current.format('YYYY-MM-DD HH:mm:ss')

    @staticmethod
    def in_last_hour(time_str: str) -> bool:
        target_time = pendulum.from_format(
            time_str, 'YYYY-MM-DD HH:mm:ss', tz='Asia/Shanghai')
        last_hour_start = pendulum.today('Asia/Shanghai').add(
            hours=(pendulum.now('Asia/Shanghai').hour - 1))
        if target_time.diff(last_hour_start).in_hours() < 1:
            elapsed_seconds = (target_time - last_hour_start).seconds
            return elapsed_seconds >= 0 and elapsed_seconds < 3600
        else:
            return False

    @staticmethod
    def log(*args, **kwargs) -> bool:
        if 'level' in kwargs:
            level_str = ['DEBUG', 'INFO', 'WARN', 'ERROR', 'FATAL']
            if isinstance(kwargs['level'], int):
                level = level_str[kwargs['level']]
            else:
                level = kwargs['level'].upper()
        else:
            level = 'INFO'
        if platform.system() == "Windows":
            os.system("")
        color_prefix = {
            'DEBUG': '\033[90m',
            'WARN': '\033[33m',
            'INFO': '\033[36m',
            'ERROR': '\033[31m',
            'FATAL': '\033[37;41m',
        }
        print(f'{color_prefix[level]}{Utils.now()}',
              '{:>7}'.format(f'[{level}]'), *args, '\033[0m')
        return

    @staticmethod
    def init_task() -> None:
        cache_path = r'./cache'
        if not os.path.exists(cache_path):
            os.mkdir(cache_path)
        return


class Config:

    def _load_config(self) -> bool:
        config_path = r'./config.json'
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.loads(f.read())
                Utils.log('已读取配置文件')
                if 'debug' in config and config['debug']:
                    self.debug = True
                else:
                    self.debug = False
                if not ('discord' in config and 'telegram' in config):
                    Utils.log('配置文件缺失必要的项目', level='error')
                else:
                    if 'enable' in config['discord'] and config['discord']['enable']:
                        if not ('webhook' in config['discord']) \
                                or config['discord']['webhook'] == '':
                            Utils.log('启用了 Discord 通知但没有配置 webhook',
                                      level='error')
                            return False
                    self.discord = config['discord']
                    if 'enable' in config['telegram'] and config['telegram']['enable']:
                        if not ('bot_token' in config['telegram']) \
                                or config['telegram']['bot_token'] == '':
                            Utils.log('启用了 Telegram 通知但没有配置 webhook',
                                      level='error')
                            return False
                        if not ('channel_id' in config['telegram']) \
                                or config['telegram']['channel_id'] == '':
                            Utils.log('启用了 Telegram 通知但没有配置 channel_id',
                                      level='error')
                            return False
                    self.telegram = config['telegram']
                    return True
            except Exception as e:
                Utils.log(e, level='error')
                print('可能解析配置文件失败 请检查 JSON 格式是否合法')
        else:
            Utils.log('配置文件缺失', level='error')
            print('运行 cp config.example.json config.json 并修改后重新运行')
        return False

    def __init__(self) -> None:
        if not self._load_config():
            exit(1)
        if not (self.discord['enable'] or self.telegram['enable']):
            Utils.log('没有启用任何播报的频道 直接退出', level='warn')
            exit(0)


CFG = Config()


class EraGameSpider:

    @staticmethod
    def get_html(url: str, use_cache: bool = False) -> str:
        html_text = ''
        if use_cache:
            cache_file = './cache/' + url.replace('://', '_').replace('/', '_')
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    html_text = f.read()
                Utils.log(f'已读取缓存 {cache_file}', level='debug')
            except Exception as e:
                Utils.log(e, level='warn')
                resp = requests.get(url, auth=('era', 'era'))
                if resp.status_code == 200:
                    with open(cache_file, 'wb') as f:
                        f.write(resp._content)
                    Utils.log(f'已重新缓存 {cache_file}')
                    html_text = resp._content.decode('utf-8')
                else:
                    Utils.log(f'请求 {url} 失败', level='error')
        else:
            resp = requests.get(url, auth=('era', 'era'))
            if resp.status_code == 200:
                html_text = resp._content.decode('utf-8')
                Utils.log(f'请求 {url} 成功')
            else:
                Utils.log(f'请求 {url} 失败', level='error')
        return html_text

    @staticmethod
    def check_update(url: str, use_cache: bool = False) -> list:
        html = EraGameSpider.get_html(f'{url}/index.html', use_cache)
        soup = BeautifulSoup(html, 'lxml')
        page_result = []
        for table_content in soup.select('table#table'):
            # print(table_content.prettify())
            for row_data in table_content.find_all('tr'):
                raw_data = row_data.find_all('td')
                if raw_data[3].text != 'サイズ':
                    page_result.append({
                        'url': f"{url}/{raw_data[1].find('a')['href']}",
                        'file_id': raw_data[1].find('a').text,
                        'file_name': raw_data[7].text,
                        'size': raw_data[3].text,
                        'time': Utils.jst_to_cst(raw_data[4].text),
                        'desc': raw_data[2].text,
                    })
        latest_result = []
        for item in reversed(page_result):
            if Utils.in_last_hour(item['time']):
                latest_result.append(item)
        return latest_result

    @staticmethod
    def send_to_discord(data_list: list, provider: str = '', avatar_url: str = '') -> None:
        data = {'embeds': []}
        if provider != '':
            data['username'] = provider
        if avatar_url != '':
            data['avatar_url'] = avatar_url
        if len(data_list) > 10:
            Utils.log('每条消息附带最多10个嵌入式信息(embed)', level='warn')
            print("""详见 https://discord.com/developers/docs/resources/webhook#execute-webhook-jsonform-params
本来预计不会出现1小时内新增超过10个新资源的情况 懒得做额外容错了
理论上说 永远不会运行到这里 就这样吧 直接退出""")
            exit(1)
        for d in data_list:
            data['embeds'].append({
                'title': d['file_name'],
                'description':
                    f'📥 [点击下载]({d["url"]})（账号/密码均为 `era`）' +
                    f'\n`{d["file_id"]}` _{d["size"]}_',
                'footer': {'text': f'更新于 {d["time"]} CST'},
                'fields': [{'name': '附带说明', 'value': d['desc']}],
            })
        try:
            url = CFG.discord['webhook']
            if 'thread_id' in CFG.discord and CFG.discord['thread_id'] != "":
                url += f'?thread_id={CFG.discord["thread_id"]}'
            resp = requests.post(url, json=data)
            if resp.status_code == 204:
                Utils.log('已发送到 Discord')
            else:
                Utils.log(f'发送到 Discord 失败\n{resp.text}', level='error')
        except Exception as e:
            Utils.log(e, level='error')
        return

    @staticmethod
    def send_to_telegram(data_list: list, provider: str = '') -> None:
        data = {
            'chat_id': int(CFG.telegram['channel_id']),
            'parse_mode': 'HTML',
            'disable_web_page_preview': True,
        }
        for d in data_list:
            URL = f'https://api.telegram.org/bot{CFG.telegram["bot_token"]}/sendMessage'
            data['text'] = f"""日本 era 储备库 - <b>{provider}</b>

▎<code>{d['file_name']}</code>

更新于 {d['time']} CST

🏷 #生肉
📥 <a href="{d['url']}">点击直接下载</a>（账号/密码均为 <code>era</code>）
<code>{d['file_id']}</code> <i>{d['size']}</i>

{d['desc']}"""
            try:
                # import http.client as http_client
                # http_client.HTTPConnection.debuglevel = 1
                # import logging
                # logging.basicConfig()
                # logging.getLogger().setLevel(logging.DEBUG)
                # requests_log = logging.getLogger("requests.packages.urllib3")
                # requests_log.setLevel(logging.DEBUG)
                # requests_log.propagate = True
                resp = requests.post(URL, json=data)
                if resp.status_code == 200:
                    Utils.log('已发送到 Telegram')
                else:
                    Utils.log(f'发送到 Telegram 失败\n{resp.text}', level='error')
            except Exception as e:
                Utils.log(e, level='error')
        return

    @staticmethod
    def broadcast(news: list, provider: str = '') -> None:
        if len(news) > 0:
            Utils.log(f'最近更新({len(news)}作):')
            tab_size = 26
            for el in news:
                print(' ' * tab_size, '\033[92m',
                      f'{el["file_id"]} \033[32m{el["url"]}')
                print(' ' * (tab_size + 4), '\033[36m', el["file_name"],
                      f'({el["size"]}) 更新于 {el["time"]}')
                print(' ' * (tab_size + 4), '\033[37m', el['desc'], '\033[0m')
            if CFG.debug:
                Utils.log('当前配置为调试模式 只请求数据 不推送通知')
            else:
                if CFG.discord['enable']:
                    EraGameSpider.send_to_discord(news, provider)
                if CFG.telegram['enable']:
                    EraGameSpider.send_to_telegram(news, provider)
        else:
            Utils.log('没有更新')
        return

    @staticmethod
    def run(enable_cache: bool = False) -> None:
        Utils.init_task()
        provider = {'up': '其他 era 游戏资源', 'up2': '东方 era 游戏资源'}
        for path in ['up', 'up2']:
            res = EraGameSpider.check_update(
                f'http://book-shelf-end.com/{path}', enable_cache)
            EraGameSpider.broadcast(res, provider[path])


def test() -> None:
    EraGameSpider.run(True)
    return


def main() -> None:
    EraGameSpider.run()
    return


if __name__ == '__main__':
    main()
