import unittest
import requests
from bs4 import BeautifulSoup
import json

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.tools import Tool
from Kaleido.environment import get_env
from Kaleido.logger import logger

class QQSpeedCarSpider:
    """
    QQ飞车图鉴爬虫工具
    用于搜索车辆信息并解析为JSON格式
    """
    
    BASE_URL = "https://www.678.tax"
    SEARCH_URL = f"{BASE_URL}/search.php"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Referer': self.BASE_URL
        })
    
    def search_cars(self, query: str) -> list:
        """
        搜索车辆信息（支持分页）
        
        Args:
            query: 搜索关键词，如"雷诺"、"A车"等
            debug: 是否启用调试模式，打印页面结构
        
        Returns:
            list: 车辆信息列表，每个元素包含车名称、转向、平跑、摩擦系数、漂移速率和数据报告链接
        """
        all_cars = []
        page_size = 12
        
        try:
            # 获取第一页
            params = {'q': query, 'page': 1}
            response = self.session.get(self.SEARCH_URL, params=params, timeout=10)
            response.raise_for_status()

            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 解析总数
            total_count = self._parse_total_count(soup)
            logger.info(f"找到相关内容 {total_count} 个")
            
            # 计算总页数
            total_pages = (total_count + page_size - 1) // page_size
            logger.info(f"共 {total_pages} 页")
            
            # 解析第一页数据
            cars = self._parse_search_results(soup)
            all_cars.extend(cars)
            logger.info(f"第 1 页: {len(cars)} 辆")
            
            # 遍历剩余页面
            for page in range(2, total_pages + 1):
                params = {'q': query, 'page': page}
                response = self.session.get(self.SEARCH_URL, params=params, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                cars = self._parse_search_results(soup)
                
                if cars:
                    all_cars.extend(cars)
                    logger.info(f"第 {page} 页: {len(cars)} 辆")
                else:
                    logger.info(f"第 {page} 页: 无数据")
                    break
            
            logger.info(f"总计获取 {len(all_cars)} 辆车辆")
            return all_cars
            
        except requests.RequestException as e:
            logger.info(f"搜索请求失败: {e}")
            return all_cars
    
    def _parse_total_count(self, soup: BeautifulSoup) -> int:
        """
        解析搜索结果总数
        
        HTML结构:
        <div class="bg-white px-4 py-2 rounded-xl border border-gray-100 shadow-sm">
            <span class="text-xs font-bold text-gray-400">找到相关内容</span>
            <span class="ml-1 text-sm font-black text-blue-600">56</span>
            <span class="text-xs font-bold text-gray-400 ml-1">个</span>
        </div>
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            int: 搜索结果总数
        """
        # 查找包含"找到相关内容"的span
        span_found = soup.find('span', string=lambda text: text and '找到相关内容' in str(text))
        if span_found:
            # 获取父级div容器
            parent_div = span_found.find_parent('div')
            if parent_div:
                # 在父级div中查找所有span
                spans = parent_div.find_all('span')
                if len(spans) >= 2:
                    # 第二个span包含数字
                    num_text = spans[1].get_text(strip=True)
                    if num_text.isdigit():
                        return int(num_text)
        
        return 0
    
    def _parse_search_results(self, soup: BeautifulSoup) -> list:
        """
        解析搜索结果页面
        
        Args:
            soup: BeautifulSoup对象
            debug: 是否启用调试模式
            
        Returns:
            list: 解析后的车辆信息列表
        """
        cars = []
        
        # 查找所有包含数据报告链接的区域
        data_links = soup.find_all('a', href=lambda x: x and '/data/' in x)

        
        for link in data_links:
            # 获取车辆卡片容器 - 需要向上查找多层
            parent = link.find_parent('div')
            if parent:
                # 向上查找包含车辆信息的外层容器
                car_container = parent.find_parent('div', class_=lambda x: x and 'bg-white' in str(x))
                if not car_container:
                    car_container = parent.find_parent('div', class_=lambda x: x and 'rounded-xl' in str(x))
                if not car_container:
                    # 继续向上查找
                    temp_parent = parent
                    for _ in range(5):
                        temp_parent = temp_parent.find_parent('div')
                        if temp_parent:
                            if temp_parent.find(string=lambda text: text and '转向' in str(text)):
                                car_container = temp_parent
                                break
                
                if car_container:
                    car_info = self._parse_car_item(car_container, link)
                    if car_info:
                        cars.append(car_info)
                else:
                    car_info = self._parse_car_item(parent, link)
                    if car_info:
                        cars.append(car_info)
        
        return cars
    
    def _parse_car_item(self, item, data_link) -> dict:
        """
        解析单个车辆信息
        
        Args:
            item: BeautifulSoup标签对象
            data_link: 数据报告链接标签
            
        Returns:
            dict: 车辆信息字典
        """
        car_info = {
            'name': '',
            'steering': '', # 转向
            'top_speed': '',# 平跑
            'friction': '', # 摩擦系数
            'drift_speed': '', # 漂移速率
            'detail_url': ''
        }
        
        try:
            # 获取数据报告链接
            car_info['detail_url'] = self.BASE_URL + data_link['href'] if not data_link['href'].startswith('http') else data_link['href']
            
            # 调试：打印车辆容器的完整内容
            # logger.info(f"\n=== 车辆容器内容 ===")
            # logger.info(item.prettify())
            # logger.info("=== 结束 ===")
            
            # 获取车辆名称 - 从h3/h4标签获取
            name_tag = item.find(['h3', 'h4'])
            if name_tag:
                car_info['name'] = name_tag.get_text(strip=True)
                # logger.info(f"找到名称: {car_info['name']}")
            
            # 如果名称为空，尝试其他方式
            if not car_info['name']:
                name_text = data_link.get_text(strip=True)
                if name_text:
                    car_info['name'] = name_text.replace('数据报告', '').strip()
            
            # 获取属性信息
            # 属性在grid容器的div中，每个div包含标签名和span中的数值
            attr_divs = item.find_all('div', class_='text-gray-400')
            for attr_div in attr_divs:
                div_text = attr_div.get_text(strip=True)
                span = attr_div.find('span')
                if span:
                    value = span.get_text(strip=True)
                    if '转向' in div_text:
                        car_info['steering'] = value
                    elif '平跑' in div_text:
                        car_info['top_speed'] = value
                    elif '摩擦系数' in div_text:
                        car_info['friction'] = value
                    elif '漂移速率' in div_text:
                        car_info['drift_speed'] = value
            
            # 只返回有名称的车辆
            if car_info['name']:
                return car_info
            
        except Exception as e:
            logger.info(f"解析车辆信息失败: {e}")
        
        return None
    
    def _extract_value(self, text: str) -> str:
        """
        从文本中提取数值
        
        Args:
            text: 原始文本，如"转向 3.8477/7.9425"
            
        Returns:
            str: 提取的数值部分，如"3.8477/7.9425"
        """
        # 去除标签名称，只保留数值部分
        value = text.replace('转向', '').replace('平跑', '').replace('摩擦系数', '').replace('漂移速率', '').strip()
        # 去除冒号和空格
        value = value.replace(':', '').strip()
        return value
    
    def get_car_detail(self, detail_url: str) -> dict:
        """
        获取车辆详细信息
        
        Args:
            detail_url: 数据报告链接
            
        Returns:
            dict: 详细信息字典
        """
        try:
            response = self.session.get(detail_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            detail_info = {}
            
            # 获取标题
            title = soup.find('h1') or soup.find('h2')
            if title:
                detail_info['title'] = title.get_text(strip=True)
            
            # 从 article 中解析所有 section 的信息
            article = soup.find('article')
            if article:
                for section in article.find_all('section'):
                    # 提取 section 标题
                    header = section.find('div', class_=['bg-gray-50', 'font-bold'])
                    section_title = header.get_text(strip=True) if header else f"section_{len(detail_info)}"

                    # 1. 提取键值对（data-grid-item）
                    grid_items = section.find_all('div', class_='data-grid-item')
                    if grid_items:
                        section_data = {}
                        for item in grid_items:
                            spans = item.find_all('span')
                            if len(spans) >= 2:
                                key = spans[0].get_text(strip=True)
                                value = spans[1].get_text(strip=True)
                                section_data[key] = value
                        detail_info[section_title] = section_data
                        continue

                    # 2. 提取表格型数据（grid-cols 结构）
                    grid_rows = section.select('div[class*="grid-cols"]')
                    if grid_rows:
                        section_data = []
                        headers = [h.get_text(strip=True) for h in grid_rows[0].find_all('div')]
                        for row in grid_rows[1:]:
                            cells = row.find_all('div')
                            if len(cells) >= len(headers):
                                section_data.append({
                                    headers[i]: cells[i].get_text(strip=True)
                                    for i in range(len(headers))
                                })
                        detail_info[section_title] = section_data
                        continue

                    # 3. 兜底：保存 section 文本（去掉标题）
                    body_text = section.get_text(' ', strip=True)
                    if section_title in body_text:
                        body_text = body_text.replace(section_title, '', 1).strip()
                    detail_info[section_title] = body_text
            
            return detail_info
            
        except requests.RequestException as e:
            logger.info(f"获取详细信息失败: {e}")
            return {}

class AgentConfig:
    # Kaleido 配置
    # LLM 配置
    Kaleido_BASE_URL = get_env(
        "KALEIDO_LLM_BASE_URL",
        aliases=("Kaleido_BASE_URL",),
    )
    Kaleido_API_KEY = get_env(
        "KALEIDO_LLM_API_KEY",
        aliases=("Kaleido_API_KEY",),
    )
    Kaleido_MODEL = get_env("KALEIDO_LLM_MODEL", default="deepseek-v4-pro")

class AgentCore(AgentConfig):
    def __init__(self, streaming=False) -> None:
        # LLM Client
        self.llm_client = ChatOpenAI(
            base_url=self.Kaleido_BASE_URL,
            api_key=self.Kaleido_API_KEY,
            model=self.Kaleido_MODEL,
            streaming=streaming)

    def qq_speed_car_agent(self):
        spider = QQSpeedCarSpider()
        tools = [
            Tool(
                name="search_cars",
                func=spider.search_cars,
                description="搜索QQ飞车的车型列表"
            ),
            Tool(
                name="get_car_detail",
                func=spider.get_car_detail,
                description="获取QQ飞车的详细信息，其中detail_url是车辆的详细报告链接，数据来自于工具search_cars返回的detail_url"
            )
        ]

        agent = create_agent(
            model=self.llm_client,
            tools=tools,
            system_prompt="你是一个专业的QQ飞车车辆信息助手，你可以搜索QQ飞车的车型列表和获取车辆详细信息，并分析这些信息，比较不同车辆的性能。",
            debug=True
        )
        return agent


class MyTestCase(unittest.TestCase):
    def test_search_cars(self):
        """测试搜索QQ飞车车辆信息"""
        spider = QQSpeedCarSpider()
        
        # 搜索雷诺，启用调试模式查看页面结构
        cars = spider.search_cars("雷诺")
        logger.info(f"搜索到 {len(cars)} 辆车辆")
        
        if cars:
            # 打印JSON格式结果
            result_json = json.dumps(cars, ensure_ascii=False, indent=2)
            # logger.info("车辆信息:")
            logger.info(result_json)
            
            # 测试获取详细信息
            first_car = cars[55]
            logger.info(f"\n获取 {first_car['name']} 的详细信息...")
            detail = spider.get_car_detail(first_car['detail_url'])
            logger.info(json.dumps(detail, ensure_ascii=False, indent=2))
        else:
            logger.info("未搜索到车辆")

    def test_agent(self):

        #user_query = "请搜索起源爆天甲和雷诺的详细数据，注意精确匹配，对比一下性能数据，并输出报告给我"
        #user_query = "起源爆天甲和通天晓S车，性能差距会很大吗"
        #user_query = "对抗属性是什么最重要？"
        user_query = "请你分析一下QQ飞车对抗中，经典的雷诺为什么被顶级S车一碰就飞了？"
        agent = AgentCore().qq_speed_car_agent()
        result = agent.invoke({"messages": [{"role": "user", "content": user_query}]})
        logger.info(result["messages"][-1].content)


if __name__ == '__main__':
    unittest.main()
