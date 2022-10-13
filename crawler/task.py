import os
import json
import pendulum
import requests
from bs4 import BeautifulSoup
import lxml


class Utils:

    @staticmethod
    def init_task() -> None:
        cache_path = r'./cache'
        if not os.path.exists(cache_path):
            os.mkdir(cache_path)
        return

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
    def now(is_timestamp: bool = False) -> str | int:
        current = pendulum.now('Asia/Shanghai')
        if is_timestamp:
            return current.int_timestamp
        else:
            return current.format('YYYY-MM-DD HH:mm:ss')

    @staticmethod
    def in_last_hour(time_str: str) -> bool:
        target_time = pendulum.from_format(
            time_str, 'YYYY-MM-DD HH:mm:ss', tz='Asia/Shanghai')
        last_hour = pendulum.today(
            'Asia/Shanghai').add(hours=pendulum.now('Asia/Shanghai').hour)
        return (target_time - last_hour).seconds >= 0

    @staticmethod
    def in_last_week(time_str: str) -> bool:
        target_time = pendulum.from_format(
            time_str, 'YYYY-MM-DD HH:mm:ss', tz='Asia/Shanghai')
        last_week = pendulum.today('Asia/Shanghai').subtract(days=7)
        return (target_time - last_week).seconds >= 0


class Config:

    def _load_config(self) -> bool:
        config_path = r'./config.json'
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.loads(f.read())
                print(f'{Utils.now()}  [INFO] 已读取配置文件')
                if not ('discord' in config and 'telegram' in config):
                    print(f'{Utils.now()} [ERROR] 配置文件缺失必要的项目')
                else:
                    for key in ['discord', 'telegram']:
                        if 'enable' in config[key] and config[key]['enable']:
                            if not ('webhook' in config[key]) \
                                    or config[key]['webhook'] == '':
                                print(
                                    f'{Utils.now()} [ERROR] 启用了 {key} 但没有配置 webhook')
                                return False
                    self.discord = config['discord']
                    self.telegram = config['telegram']
                    return True
            except Exception as e:
                print(f'{Utils.now()} [ERROR] {e}')
                print('可能解析配置文件失败 请检查 JSON 格式是否合法')
        else:
            print(f'{Utils.now()} [ERROR] 配置文件缺失')
            print('运行 cp config.example.json config.json 并修改后重新运行')
        return False

    def __init__(self) -> None:
        if not self._load_config():
            exit(1)
        if not (self.discord['enable'] or self.telegram['enable']):
            print(f'{Utils.now()}  [WARN] 没有启用任何播报的频道 直接退出')
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
                print(f'{Utils.now()}  [INFO] 已读取缓存 {cache_file}')
            except Exception as e:
                print(f'{Utils.now()}  [WARN] {e}')
                resp = requests.get(url, auth=('era', 'era'))
                if resp.status_code == 200:
                    with open(cache_file, 'wb') as f:
                        f.write(resp._content)
                    print(f'{Utils.now()}  [INFO] 已重新缓存 {cache_file}')
                    html_text = resp._content.decode('utf-8')
                else:
                    print(f'{Utils.now()} [ERROR] 请求 {url} 失败')
        else:
            resp = requests.get(url, auth=('era', 'era'))
            if resp.status_code == 200:
                html_text = resp._content.decode('utf-8')
                print(f'{Utils.now()}  [INFO] 请求 {url} 成功')
            else:
                print(f'{Utils.now()} [ERROR] 请求 {url} 失败')
        return html_text

    @staticmethod
    def check_update(url: str, debug: bool = False) -> list:
        html = EraGameSpider.get_html(f'{url}/index.html', debug)
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
        if debug:
            print(f'{Utils.now()} [DEBUG] 已启用调试模式 返回的结果为最近一周')
        for item in reversed(page_result):
            if debug and Utils.in_last_week(item['time']):
                latest_result.append(item)
            elif Utils.in_last_hour(item['time']):
                latest_result.append(item)
        return latest_result

    @staticmethod
    def send_to_discord(data_list: list, username: str = '', avatar_url: str = '') -> None:
        data = {'embeds': []}
        if username != '':
            data['username'] = username
        if avatar_url != '':
            data['avatar_url'] = avatar_url
        if len(data_list) > 10:
            print(f'{Utils.now()}  [WARN] 每条消息附带最多10个嵌入式信息(embed)')
            print(
                '详见 https://discord.com/developers/docs/resources/webhook#execute-webhook-jsonform-params')
            print('本来预计不会出现1小时内新增超过10个新资源的情况 懒得做额外容错了')
            print('理论上说 永远不会运行到这里 就这样吧 直接退出')
            exit(1)
        for d in data_list:
            data['embeds'].append({
                'title': d['file_name'],
                'description':
                    f'[点击下载]({d["url"]})（账号密码均为 `era`）' +
                    f'\n`{d["file_id"]}` _{d["size"]}_',
                'footer': {'text': f'更新于 {d["time"]}'},
                'fields': [{'name': '附带说明', 'value': d['desc']}],
            })
        try:
            resp = requests.post(CFG.discord["webhook"], json=data)
            if resp.status_code == 204:
                print(f'{Utils.now()}  [INFO] 已发送到 Discord')
            else:
                print(f'{Utils.now()} [ERROR] 发送到 Discord 失败 {resp.text}')
        except Exception as e:
            print(f'{Utils.now()} [ERROR] {e}')
        return

    @staticmethod
    def send_to_telegram(data_list: list) -> None:
        print('TODO 发送到 Telegram', CFG.telegram["webhook"])
        return

    @staticmethod
    def broadcast(news: list, username: str = '') -> None:
        if len(news) > 0:
            print(f'{Utils.now()}  [INFO] 最近更新({len(news)}作):')
            tab_size = 27
            for el in news:
                print(' ' * tab_size, el['file_id'], el['url'])
                print(
                    ' ' * (tab_size + 4),
                    el["file_name"],
                    f'({el["size"]}) 更新于 {el["time"]}',
                )
                print(' ' * (tab_size + 4), el['desc'])
            if CFG.discord['enable']:
                EraGameSpider.send_to_discord(news, username)
            if CFG.telegram['enable']:
                EraGameSpider.send_to_telegram(news)
        else:
            print(f'{Utils.now()}  [INFO] 没有更新')
        return

    @staticmethod
    def run(debug: bool = False) -> None:
        Utils.init_task()
        username = {'up': '其他era游戏', 'up2': '东方era游戏'}
        for path in ['up', 'up2']:
            res = EraGameSpider.check_update(
                f'http://book-shelf-end.com/{path}', debug)
            EraGameSpider.broadcast(res, username[path])


def test() -> None:
    EraGameSpider.run(True)
    return


def main() -> None:
    EraGameSpider.run()
    return


if __name__ == '__main__':
    main()
