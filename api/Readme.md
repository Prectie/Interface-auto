
## 项目结构总览
项目采用模块化结构，将页面对象、核心功能、工具类、测试数据等分别存放。各模块目录结构及作用如下：
```markdown
ProjectRoot/
├─ Base/ # 框架底层封装
│ ├─ base.py                  # 基础类，负责初始化 WebDriver 实例和定位器字典，管理各类 Mixin 实例。
│ ├─ Core/                    # 核心功能子模块，包含最底层的封装实现。
│ │ ├─ locator_provider.py    # LocatorMixin，定位器处理，提供获取/格式化定位器方法
│ │ ├─ selenium_element.py    # ElementMixin，二次封装 selenium，继承 LocatorMixin，实现统一的元素查找和等待逻辑
│ │ └─ ec_extension.py        # 针对 selenium EC 模块的自定义扩展模块
│ └─ Facade/                  # 对外提供基础功能接口子模块
│ │ ├─ element_operator.py    # 元素基本操作封装，继承 ElementMixin，提供大量以元素基础操作方法（点击、输入、获取文本等）
│ │ ├─ browser_operator.py    # 浏览器操作封装，继承 ElementMixin，提供浏览器级操作方法，如打开 URL、窗口切换、刷新等。
│ │ ├─ mouse_action.py        # 鼠标模拟操作封装，继承 ElementMixin，提供悬停点击、双击、拖拽等高级鼠标动作方法
│ └─└─ wait_operator.py       # 通用等待操作封装，继承 ElementMixin，提供特定场景的等待方法，如等待属性值出现、等待元素过时等
├─ Data/                      # 测试数据目录
│ ├─ demo.yaml                # 示例 YAML 测试数据文件
│ └─ ...                      # 其他测试数据文件
├─ Enum/                      # 枚举类型, 提供一些常用常量
│ ├─ attribute_value.py       # HTML 属性名中存在的属性值
│ ├─ attribute.py             # 存放 HTML 标签里的各种属性名
│ ├─ css_property.py          # CSS 属性名
│ ├─ url.py                   # 常用的 URL 路径
│ └─ wait_strategy.py         # selenium底层封装实现策略选项
├─ Fixtures/                  # 测试夹具配置模块。定义 Pytest 的 fixture 函数及钩子。
│ ├─ browser_fixtures.py      # 定义与浏览器启动和页面入口相关的 fixture，如提供 WebDriver 实例，提供页面等。
│ └─ func_fixtures.py         # 定义通用的功能性 fixture 或钩子。如 pytest_runtest_makereport 钩子实现用例失败截图并附加报告
├─ Log/                       # 日志文件目录（运行时自动生成）
├─ Page/                      # 页面对象模块
│ ├─ base_page.py             # BasePage抽象类，所有具体页面类的父类，提供通用方法
│ ├─ pages_entry.py           # PageEntry页面入口，统一管理页面对象的获取，内部通过懒加载机制管理所有页面对象的实例
│ ├─ CommonPage/              # （示例）公共页面模块
│ │ └─ login_page.py          # 登录页面类（示例）
│ ├─ demo_page.py             # Demo页面类（示例）
│ └─ ...                      # 其他页面对象文件
├─ Screenshot/                # 失败截图保存目录（运行时自动生成）
├─ Snapshots/                 # 图像识别保存目录
├─ Tests/                     # 测试用例目录
│ ├─ test_demo.py             # 测试用例示例（使用 Pytest）
│ └─ ...                      # 其他测试用例
├─ Utils/                     # 工具类模块
│ ├─ driver_utils.py          # 浏览器驱动工具，提供 open_browser 等方法
│ ├─ log_utils.py             # 日志工具，封装 nb_log 日志初始化和存储
│ ├─ analyze_utils.py         # 测试数据解析工具，提供读取 YAML 数据等函数
│ └─ ...                      # 其他工具（如文件路径查找、偏移量计算等），根据需要添加
├─ pyproject.toml             # Pytest 配置文件（设置默认参数、标记等）
└─ run.py                     # 一键运行测试并生成报告的入口模块
```

**测试人员主要关心的：**
- Base/ 下的各 Mixin 类（LocatorMixin、ElementMixin、KeywordMixin 等）负责核心关键字动作的实现。通过多重继承或组合，这些Mixin为页面对象提供了封装良好的 click_by_keyword 、 input_by_keyword 、 switch_iframe_by_keyword 等方法（不需要背，需要什么查找即可，所有方法均提供了良好的注释），屏蔽了底层等待、元素查找细节，提高用例稳定性。
- Page/ 下包含页面对象定义： 
  - BasePage 抽象类提供所有页面通用的属性和方法（例如统一的 _locators 字典合并逻辑、常用断言方法等），**具体页面类需继承它**。 
  - PageEntry 这是整个框架的页面入口管理器。 PageEntry 内部映射了页面名称到对应的页面类，可通过惰性加载的方式获取页面实例（如 entry.LoginPage ）。它确保在需要时才初始化页面对象，并复用同一测试中的页面实例。
  - 各页面类（如 LoginPage , DemoPage ）在类属性中定义自己页面的 **_locators 字典** 和 **页面操作方法**。例如 LoginPage 定义登录页的元素定位器，以及封装了登录操作的 login() 方法。
- Tests/ 目录存放实际的测试脚本。测试文件以 test_*.py 命名，使用 Pytest 风格编写，用 fixture 注入需要的页面对象、驱动等。
- Utils/ 模块提供各种工具函数： 
  - log_utils.py 利用 nb_log 封装日志记录功能。 LoggerManager.get_logger() 会自动在项目根目录下创建 Log/ 文件夹，并生成按命名空间区分的日志文件（如 default.log 和 default_error.log），方便调试。 
  - analyze_utils.py 提供读取测试数据的功能，具体方法见源码注释。
  - calculate_offset_utils.py 提供计算 元素a 到 元素 b 的偏移量，以达到拖拽元素的目的。
  - ... 其他工具方法，需要时再用，上述三个工具类是需要重点关注的
- pyproject.toml 文件对 Pytest 进行配置，例如默认测试路径、参数 -vs 、并行策略、失败重跑策略，以及自定义的 markers 等。 
- run.py 提供了一键运行所有测试并生成报告的入口脚本。运行该脚本将执行 Tests/ 下所有测试，并自动生成 Allure 报告文件和启动本地服务器查看报告。

---
## 环境配置
要使用本框架，请确保以下环境和依赖配置正确：
- Python 版本：需要 Python 3.x（建议 3.8 及以上）环境。
- 浏览器驱动：根据所测浏览器安装对应的WebDriver驱动程序。例如使用Chrome浏览器，请下载与
Chrome版本匹配的 ChromeDriver，并确保可执行文件路径在代码中配置或添加到系统 PATH。框架
默认使用Chrome（可通过命令行参数切换浏览器，详见后文）。
- 依赖安装：在项目根目录下执行以下命令安装所需依赖库：
  ```markdown
  pip install --no-index --find-links=./packages -r requirements.txt
  ```
- Allure 环境：为了生成和查看 Allure 报告，需要预先安装 Allure Commandline 工具，并将其加入系统环境变量。确保在命令行中能运行 allure 命令（可通过 allure --version 验证）。
- 项目配置：根据需要，修改 Utils/driver_utils.py 中浏览器驱动路径设置。例如ChromeDriver路径默认写在代码中 ( Service("C:/Program Files/chrome-win64/chromedriver.exe") )，请修改为实际路径或确保该路径下存在驱动。Firefox类似，如未配置Firefox驱动路径则默认使用Chrome启动。

完成上述环境准备后，即可编写和运行测试用例。

---
## 快速开始
按照以下步骤快速启动测试并查看结果：
1. 运行测试： 可以直接使用 Pytest 命令运行所有测试：
    ```bash
    pytest
    ```
    默认情况下，Pytest 会根据 `pyproject.toml` 的配置发现并执行 Tests/ 目录下的用例。
    常用选项：
      - `-vs`：控制台打印更详细的日志信息（来源于 nb_log）并保持标准输出，便于调试。
      - `--mybrowser=<browser>` : 指定浏览器运行测试，不指定则默认为 Chrome。支持的值有 chrome 或 firefox 等，例如：
         ```bash
         pytest -vs --mybrowser=firefox
         ```
         该参数由框架注册的自定义选项提供，用于在运行时动态切换浏览器驱动。
      - 如果希望临时运行特定脚本，可在命令后加 -k 过滤（其中也包含标记名、fixture名，因此只适合临时运行）：
        ```bash
        # 运行名中含 login, 且不含 slow 的用例
        pytest -k "login and not slow" -vs
        ```
2. 使用脚本运行：项目提供了 run.py 脚本实现一键执行测试并生成报告：
   ```bash
   python run.py
   ```
   该脚本会按以下流程自动执行：
     - 调用 `pytest.main` 运行 Tests/ 下所有用例，并生成 Allure 报告的中间结果至 `allure_json_report/<时间戳>/` 目录。
     - 测试执行完毕后，使用 Allure 工具将上述结果生成可视化的HTML报告至 `allure_report/<时间戳>/` 目录（如果已存在则清理后重建）。
     - 自动启动 `allure serve` 打开临时服务器，在浏览器中打开生成的报告。报告中包含测试步骤、断言结果以及截图等附件。
3. 生成与查看 Allure 报告：如果不使用 `run.py` 脚本，也可以手动生成报告：
   - 首先执行 `pytest --alluredir=allure_json` 运行测试并输出 Allure 的原始结果文件到指定目录（如 `allure_json` ）。
   - 然后运行 `allure generate allure_json -o allure_report --clean` 将结果生成静态报告文件到 `allure_report` 目录。
   - 最后运行 `allure open allure_report` 或 `allure serve allure_json` 来启动本地服务查看报告。 Allure 报告详细展示每个测试用例的步骤、日志和附件，便于分析测试结果。
   - 若已存在 allure 原始文件或静态报告，用 Allure CLI 打开静态报告：
     ```bash
     allure open .\allure_report\<文件名> 
     ```
     只有原始文件的情况：
     ```bash
     allure serve .\allure_json_report\<文件名> 
     ```

---
## 编写用例说明
本框架采用 Page Object 模式组织代码和用例。编写测试用例时，需要按照以下步骤进行：
1. **新增页面类并定义定位器**：当被测应用新增页面或模块时，应当为其创建对应的页面类。
   - 在 `Page/` 目录下新建相应的Python文件，并定义页面类继承自 `BasePage` 。
   - 在类中声明 `_locators` 字典属性，用于存储该页面所有需要操作的元素定位方式。键名应具备语义，通常以操作或元素类型为前缀（例如： `"action_登录按钮"` 表示登录按钮， `"query_成功提示"` 表示用于查询断言的成功提示元素）。键值可以是：
     - XPath/CSS选择器字符串（框架会默认按 By.XPATH 处理单个字符串，这也是框架统一使用的选择器格式）
     - 或包含定位方式的元组，如 `(By.ID, "element-id")`
     - 或列表（用于多级定位或iframe嵌套定位，每一级一个定位器）。
   - 确保 `_locators` 包含所有在该页面可能被操作或断言的元素。定义完成后，无需手动初始化 WebElement，框架会根据关键字自动查找元素。
2. **实现页面方法**：在页面类中，根据业务需求封装用户操作流程的方法，以便测试用例直接调用。
   - 典型的页面方法会利用框架提供的关键字操作函数执行一系列动作。例如在登录页面类 `LoginPage` 中实现 `login(username, password)` 方法：通过 `self.base.具体Facade操作` 调用关键字方法输入用户名、输入密码并点击登录按钮。示例如下：
     ```python
     class LoginPage(BasePage):
         _locators = {
            "action_账号输入框": "//input[@placeholder='账号']",
            "action_密码输入框": "//input[@placeholder='请输入密码']",
            "action_登录按钮": "//*[contains(@class, 'login-btn')]",
         }
     
        def login(self, username, password, times: int = 1):
            self.base.element_op.clear_and_input_by_keyword('action_账号输入框', value=username)
            self.base.element_op.clear_and_input_by_keyword('action_密码输入框', value=password)
            self.base.element_op.click_by_keyword("action_登录按钮")
     ```
     上述 `input_by_keyword` 和 `click_by_keyword` 由框架关键字驱动提供，它们会自动等待元素出现并可点击后再执行操作，避免直接使用 `driver.find_element().click()` 所导致的同步问题。注意：`self.base` 是 Base 类实例，通过组合包含关键字方法；也可以在页面类中直接继承相应 Mixin 来调用方法，但推荐使用组合的 `self.base` 来统一管理。
   - 若页面有特定功能需要返回数据或状态，例如截取某区域截图、获取文本列表等，可以在页面方法中调用框架提供的 `get_element_text_by_keyword` 、 `screenshot_element_by_keyword` 等方法，将结果返回给测试用例。
3. **在 PageEntry 中注册页面**：打开 `Page/pages_entry.py` ，将新建的页面类导入并添加到`PageEntry._map` 字典中。这样测试用例才能通过 `entry.页面类名` 访问该页面对象。例如：
   ```python
   from Page.new_page import NewPage # 导入新页面类
   class PageEntry:
    # ... 已有内容
   
    # 显式声明所有 page 属性, 增强IDE编写提示
    BasePage: BasePage  
    LoginPage: LoginPage
    DemoPage: DemoPage
    NewPage: NewPage  # 添加映射
   
    _map = {
        'BasePage': BasePage,
        'LoginPage': LoginPage,
        'DemoPage': DemoPage,
        'NewPage': NewPage  # 添加映射
    }
   
   # ...
   ```
4. **编写测试用例**：在 `Tests/` 目录下创建或修改测试文件，按照Pytest的格式编写函数或类。
   - 注入fixture：测试函数的参数中声明需要使用的 fixture 名称。常用的有：
     - `entry`：框架提供的页面入口 `PageEntry` 实例（function 级，每个测试用例函数都会得到一个新的 PageEntry）。通过它访问各页面对象。
     - `image_snapshot`：截图断言fixture，用于进行图像比对（详见后文截图断言部分）。
   - 使用页面对象调用其方法：通过 `entry.XxxPage` 获取页面对象后，可直接调用先前封装的页面方法执行操作。例如：
     ```python
     def test_login_success(self, entry):
        # 通过 entry 获取 LoginPage 对象并执行登录动作
        entry.LoginPage.login("testuser", "password123")
        # 切换到登录后页面，执行进一步验证
        assert entry.DashboardPage.is_loaded()
     ```
     如上所示， `entry.LoginPage` 首次被访问时会初始化 LoginPage 实例并返回，以后再次访问将重用缓存对象。调用 `login()` 方法后，可以继续通过 `entry` 获取其它页面对象进行操作或断言。
   - 使用 fixture 数据：若测试需要参数化数据驱动，可利用 `@pytest.mark.parametrize` 装饰器结合 `Utils.analyze_utils` 中的函数。从 YAML 文件读取测试数据。例如：
     ```python
     @pytest.mark.parametrize("data", combine_same_file_key(["common_account", "search_data"], "demo.yaml"))
     def test_search(self, entry, data):
         entry.LoginPage.login(data['username'], data['password'])
         results = entry.SearchPage.search(data['keyword'])
         assert data['expected'] in results
     ```
     上述例子中，`combine_same_file_key(["common_account", "search_data"], "demo.yaml")` 会读取 Data/demo.yaml 文件中 `common_account` 和 `search_data` 两关键字的数据，做笛卡尔积组合生成测试数据列表，实现多组账号与搜索词的组合测试。Pytest会根据生成的数据列表多次调用该测试函数，分别传入 `data` 参数。
5. 运行测试并观察结果：执行 `pytest` 运行编写的用例，确保它们通过。Allure 报告将展示每一步操作（如果有 `@allure.step` 装饰）以及断言结果。出现失败时，可查看 Allure 报告中的日志和自动截图定位问题。

通过以上步骤即可编写新的测试用例。总结来说，**先在页面对象层封装动作，再在测试层调用，高内聚低耦合，便于维护**。

---
## 关键功能演示
框架封装了Web UI自动化中常用的关键功能（本节仅简要介绍常用的功能，其他功能请见 Base/Facade/ 目录下的模块文件），以下对这些功能的使用方法和原理做简要说明：

### 1.点击、输入操作与断言（关键字驱动）
框架通过关键字驱动封装了元素交互操作，测试脚本无需直接调用 Selenium 的 `find_element` 或 `click` 等方法，而是使用更高层的关键字函数，这些函数内部统一做了显式等待和异常处理。常见操作包括：
- 点击 ( `click_by_keyword` )：根据定位器关键字点击元素。示例：
  ```python
  self.base.element_op.click_by_keyword("action_登录按钮")
  ```
  调用时传入在 `_locators` 定义的键名（如 `action_提交按钮` ），框架会自动找到对应定位器，等待元素可点击 ( `WaitStrategy.CLICKABLE` ) 后执行 `el.click()` 。如果需要点击一组元素中的部分元素，还提供 `click_slice_by_keyword()` 按照 Python 切片格式来点击
- 输入 ( `input_by_keyword` )：根据定位器关键字对元素发送文本输入。示例：
  ```python
  self.base.element_op.input_by_keyword("action_登录按钮", value="testuser")
  ```
  此方法会等待元素可见可交互后，执行 `el.send_keys(value)` ，输入指定文本。相比直接调用 Selenium 的 `send_keys` ，框架封装可避免元素未加载就输入、输入过程中碰到Stale Element等问题。
- 获取文本/属性：使用 `get_text_by_keyword()` 、 `get_value_by_keyword()` 等方法可直接获取元素的文本值或属性值。例如 `self.base.element_op.get_text_by_keyword("query_用户名")` 返回用户名标签文本， `self.base.element_op.get_value_of_css_property(keyword, "display")` 可获取CSS属性值。这些方法同样内置等待，确保元素存在后再获取值。

上述关键字操作与断言方法都使用了统一的等待机制（通过 WaitStrategy 枚举指定等待策略）。在调用这些方法时，可以通过可选参数调整等待超时时间、轮询频率等。例如：
```python
self.base.element_op.clear_and_input_by_keyword('action_密码输入框', value=password, timeout=10, poll_frequency=0.5, ignored_exceptions=NoSuchElementException)
```
该方法等待时间变为10秒，轮询时间变为每轮0.5秒，需要单独处理的异常为 `NoSuchElementException`。

但大部分情况下无需手动传这些参数，使用默认等待已能满足稳定性要求。

框架还利用 Allure 的 step 机制对关键步骤方法添加了说明。例如 LoginPage 的 `login()` 方法上有 `@allure.step("执行 登录 操作")` 装饰，这意味着在 Allure 报告中，此方法调用会显示为一个步骤，并记录参数 expected 的值，帮助测试人员直观了解执行了什么操作。

---
### 2.iframe 切换
Web应用中经常使用嵌套的 `<iframe>` ，框架在关键字驱动中提供了便捷的方法进行 iframe 的进入和退出：
- **进入 iframe**：使用 `switch_iframe_by_keyword(keyword)` 切换进入指定的 iframe。只需在
  `_locators` 定义中为该iframe元素起一个关键字（例如 `"iframe_编辑区域": "//iframe[@id='editFrame']"` ），然后调用：
  ```python
  self.base.element_op.switch_iframe_by_keyword("iframe_编辑区域")
  ```
  框架会等待该 iframe 存在且可切换，然后将 Selenium 的上下文切换进去。**支持多级iframe**：如果`_locators` 对应的值是一个字符串列表，表示嵌套的多层iframe路径，函数会按顺序依次进入每一层 iframe。
- 切换 iframe：提供两种快捷方式：
  - `switch_default_iframe()` 切换回最顶层的默认内容。调用此方法后，Selenium 会回到主页面。
  - `switch_parent_iframe()` 切换到上一层父iframe，如果当前已经在顶层则无效果。这两个方法在内部也通过 WaitStrategy 做了适当的处理，确保切换成功。

使用iframe切换示例：
```python
self.base.element_op.switch_iframe_by_keyword("iframe_编辑区域")
# 执行其他操作...
self.base.element_op.switch_default_iframe()
```
如上，首先进入名为编辑区域的iframe，执行内部操作，然后切回默认主页面。框架方法封装了显式等待逻辑，如果在指定时间未能成功切换，将抛出超时异常以便测试用例捕获处理。

---
### 3.页面对象懒加载
`PageEntry` 实现了页面对象的懒加载和缓存，这是框架提升性能和避免重复初始化的重要特性。
- 懒加载：当在测试用例中首次通过 `entry.XxxPage` 访问某页面时， `PageEntry.__getattr__` 会拦截属性调用： 
  - 根据属性名（页面类名）在 `_map` 字典中找到对应的页面类。 
  - 使用当前的 WebDriver实例（以及下载目录等必要参数）初始化该页面类，创建页面对象。 
  - 将该对象缓存到 `PageEntry._cache` ，并返回给调用处。
- **缓存复用**：在**同一个测试用例**中，如果再次访问相同的 `entry.XxxPage` 属性， `__getattr__` 会直接从`_cache` 返回已创建的实例，而不会重复初始化。这确保了在一次测试流程中，同一页面对象的状态能被保存和复用（例如已经登录的页面对象可以复用），避免不必要的开销。

**好处**：懒加载使得测试启动时无需初始化所有页面，提高了效率；而缓存避免了重复登录或重复打开页面。如果确实需要重新实例化页面（比如要回到初始状态），可以手动删除 `entry._cache` 中对应项，但通常不需要 这样做。

需要注意的是， `entry` 本身是 function 作用域的 fixture，每个测试用例都会得到一个新的 PageEntry 实例。因此不同测试之间页面对象不会相互影响，保证了测试独立性。同时，每个测试完成后 `entry` 即会销毁，其中缓存的页面对象也会随之释放，防止状态“泄漏”到下一个测试。

---
### 4.数据驱动测试
框架鼓励使用数据驱动来覆盖更多组合场景， Utils/analyze_utils.py 提供了便捷的方法读取测试数据，支持 YAML 文件定义多组参数。典型用法:
-  **YAML测试数据组织**：在 **Data**/ 目录下创建 YAML 文件，例如 demo.yaml，用文档划分不同的数据集：
   ```yaml
   common_admin_account:
      - username: "admin"
        password: "123456"
   demo_e:
      - tree_node: "节点A"
      - tree_node: "节点B"
   ```
   上述文件中定义了两个key： `common_admin_account` 包含账号密码列表， `demo_e` 包含不同的树节点名称列表。
- **combine_same_file_key**：函数 `combine_same_file_key(keys, filename, mode=)` 可以读取同一 YAML 文件中多个key的数据列表，根据 `mode` 返回 笛卡尔组合（'cartesian'） 或 数据拼接（'zip'）。例如：
   ```python
   test_data = combine_same_file_key(["common_admin_account", "demo_e"], "demo.yaml", mode='cartesian')
   ```
  将返回一个列表，其中每个元素是合并后的字典，如：
   ```python
   [
      {"username": "admin", "password": "123456", "tree_node": "节点A"},
      {"username": "admin", "password": "123456", "tree_node": "节点B"}
   ]
   ```
  然后在 `pytest.mark.parametrize` 中使用这个列表，实现参数化测试。Pytest会对列表中的每个数据项运行一次测试函数，将对应字典传给参数 data。

- **其他数据组合**：除了简单两组数据组合， analyze_utils.py 还提供了更灵活的读取数据方法，具体见源码，源码中提供了良好的注释。

数据驱动让测试用例更简洁，不同测试数据与逻辑分离，提高用例覆盖率。结合参数化，每条测试数据的执行结果都会在Allure报告中体现，有助于定位哪组数据出现问题

---
### 5.截图断言（视觉比对）
框架集成了截图比对功能，使测试可以对页面UI进行视觉回归校验。通过 `image_snapshot` fixture，可方便地将实际页面截图与期望截图进行对比：
- **获取实际截图**：框架封装方法方便获取元素或区域截图。例如使用 `screenshot_element_by_keyword(keyword, filename)` 可将对应元素截屏保存为文件。也可以通过 Selenium原生方法获取整个页面截图。测试中常见做法是：在页面对象方法中调用截图函数并返回截图文件路径或图像对象。例如示例中的 entry.DemoPage.action() 方法，进行了某些操作后调用`.crop()` 截取结果区域，将截图路径返回给测试用例。
- **调用 image_snapshot 进行比对**：在测试函数中，将实际截图和期望截图路径传给`image_snapshot(actual, expected, threshold=<阈值>)`：
   ```python
   cropped_image = entry.DemoPage.action(...)
   image_snapshot(cropped_image, "D:/orp-auto-test/ORP/Snapshots/test_image.png", threshold=0.1)
   ```
  其中 `cropped_image` 是实际截图文件路径（或图像对象），第二个参数是预期图像的文件路径。`threshold` 是允许的差异阈值（0.0～1.0之间，表示不同比例），缺省值通常很小（例如0.1表示允许10%的像素差异）。 `image_snapshot` 会将两张图像进行像素级比较：
    - 如果差异在阈值以内，则断言通过，测试继续。 
    - 如果差异超过阈值，则判定断言失败。通常框架会将差异部分高亮并生成对比图，保存到指定位置（或默认的Snapshots/目录），同时在Allure报告中附加该对比图片，方便查看哪里出现了不一致。

使用注意：在进行图像比对前，需要先准备好 “期望截图” 作为基准文件，通常保存在项目的 Snapshots 目录中。初次运行测试可能没有期望截图，该 fixture 会将首次截图当做基准。后续运行中，如果UI发生变化，报告中的对比图能直观体现差异，便于判断是否为预期变动。

此外，pyproject.toml 中可以设置 `--image-snapshot-save-diff` 等选项，确保当截图比对失败时，将差异图自动保存。这在持续集成中很有用，失败时也能事后拿到对比图进行分析。

通过截图断言，可以覆盖纯功能测试难以验证的UI变化，例如样式是否渲染正确、图标是否显示等，提升测试覆盖的深度。

---
## 日志与截图说明
为了辅助调试和结果分析，框架对日志记录和失败现场截图提供了支持：
- **日志记录（nb_log）**：框架使用 `nb_log` 库集中管理日志。通过 `Utils/log_utils.py` 中的`LoggerManage ，每次运行测试会在项目根目录下自动创建 Log/ 文件夹： 
  - **运行日志**：默认命名为 `default.log`（或自定义名称的 .log），记录INFO级别以上的信息，包括每一步操作、等待、结果等内容。 
  - **错误日志**：对应 `default_error.log` 文件，记录ERROR级别的错误栈和断言失败等关键信息。`LoggerManager`会根据调用日志的模块自动划分日志文件名，避免不同测试模块的日志混杂在一起。日志格式经过设置，包含时间、线程、日志级别和消息，便于阅读。在 pytest -vs 模式下，这些日志也会实时输出到控制台。团队成员调试时可查阅 Log/ 中的文件获取详细的执行过程记录。 
- **失败截图自动保存**：框架利用 Pytest 提供的 hook，在每个用例执行完毕后检查其结果。如果测试失 败，则自动截取浏览器当前页面的截图： 
  - 实现在 `Utils/func_fixtures.py` 中，通过 `pytest_runtest_makereport` 钩子，在用例失败且处于 call 阶段时，获取 `driver` 对象，调用 `driver.get_screenshot_as_png()` 截图。 
  - 将截图以 `<用例名称>_<时间戳>.png` 命名，保存到项目根目录下的 **Screenshot/** 文件夹。同时调用`allure.attach()` 附加该截图到 Allure 报告中。这样，在查看 Allure 报告时，每个失败用例下会有一个截图附件，点击即可查看当时页面的样子。 
  - 此过程完全自动，无需测试人员干预。若获取 `driver` 失败（例如fixture未提供），会记录错误日志。

通过上述日志和截图机制，发生错误时测试人员可以方便地获取详细信息：日志提供了操作顺序和数据，截图 还原了失败时页面状态。这对分析定位问题非常有帮助。例如，某元素找不到，可以从截图中发现页面是否跳转有误；或者从日志中看到等待了多久超时等细节。

日志文件和截图文件会在每次运行累积保存，需要定期清理过旧的数据，以防止占用过多存储。

---
## 注意事项

为充分发挥本框架的效率和稳定性，编写测试时请遵循以下注意事项：

- **页面类划分清晰**
  - 确保每个页面（或页面的一部分）都有对应的Page类和 `_locators` ，不要在一个类中混入太多不同页面的元素。这样可以最大程度地重用页面方法，并使维护定位器更加方便。不要在测试用例中直接使用硬编码的定位器定位元素，应统一通过页面对象获取元素，以实现定位器集中管理。

- **通过 PageEntry 获取页面实例**
  - 永远使用框架提供的 `entry.XxxPage` 来获取页面对象，而不要自行实例化页面类（除非特殊情况需要绕过框架）。这样可以利用框架的懒加载和缓存，避免重复初始化带来的性能和状态问题。例如，即使需要在测试中多次进入登录页面执行操作，也应反复使用同一个`entry.LoginPage` 实例，而非每次创建新对象。 

- **充分利用关键字方法**
  - 框架封装的大部分 Web 操作，如点击、输入、选择下拉、切换iframe等，都提供了对应的关键字驱动方法。**尽量避免直接调用 Selenium WebDriver 提供的底层API** (如`find_element` , `click` , `send_keys` 等) 在测试代码中操作元素。一方面，框架方法内部实现了更健壮的等待重试机制，可减少脚本由于同步问题失败的概率；另一方面，使用关键字方法能提高代码可读性，让测试步骤更接近业务语言。例如，使用 `entry.CartPage.base.click_by_keyword("action_删除商品")` 比 `driver.find_element(By.XPATH, "...").click()` 更直观说明操作意图。

- **Fixture 和上下文管理**
  - 遵循Pytest fixture的使用方式，不要在测试中手动创建或销毁 WebDriver 实例。框架提供的 `driver` fixture 已负责启动浏览器并在会话结束时关闭。类似地， `entry` fixture保证每个测试函数独立的页面入口。善用这些fixtures可以确保测试环境的干净和稳定。如果有前置步骤（如登录）、后置清理等需求，可以利用 Pytest markers 或者在 BasePage/page方法中封装通用操作，而避免在每个用例里重复编写。

- **元素定位策略**
  - 在 `_locators` 中编写定位器时，尽量使用稳健的选择器，例如添加明确的属性限定或使用层级关系，避免仅通过文本或位置定位不稳定元素。可以使用 XPath 的模糊匹配（例如包含文本）来定位动态文本元素。框架默认未指定定位方式的字符串按 XPath 处理，如需用 CSS Selector 或 ID，可以使用 `(By.CSS_SELECTOR, "#id")` 这样的形式。

- **等待策略**
  - 框架提供了多种等待策略 ( `WaitStrategy` 枚举)，默认针对大多数操作使用了合理的等待（如点击前等待元素可点击，获取元素列表前等待可见等）。特殊情况下可以手动指定，如等待文本出现、等待元素消失等，可调用对应的方法或在关键字方法参数中传入 `wait_strategy` 。尽管框架已尽可能减少显式 `sleep` 的需要，但在极少数情况下，可能需要在测试步骤中插入短暂等待来等待后台进程完成，这时也应使用 WebDriverWait 或框架封装的等待方法，而非 `time.sleep` 。

- **组织测试代码**
  - 测试用例应尽量保持简洁清晰，每个用例只关注验证一件业务功能。将重复的前置步骤（如登录）通过 fixture 或调用封装好的页面方法来实现。可以使用 Pytest 的 `marks` 来控制某些用例是否执行（比如慢速的UI测试可以标记分类）。合理使用 `parametrize` 和数据文件，让一份测试逻辑覆盖多组数据。

- **报告与调试**
  - 善用 Allure 报告能力。在需要的时候，可以在测试步骤中插入 `allure.step` 或 `allure.attach` 去记录重要信息（框架内部已经在关键页面方法使用了 allure.step）。比如在数据驱动测试里，可以attach当前输入的数据详情。当用例失败时，充分利用日志和截图进行分析，并及时更新断言的期望值或页面定位器，以适应产品变化。

- **定位器命名规则**
  - **操作器**(Action):所有可交互元素(点击/输入/提交),如：按钮，输入框，可点击元素等
  - **读取器**(Query):仅用于获取信息(文本/属性/状态),如：纯展示的元素
  - **导航器**(Context):需要切换上下文的容器，如：下拉菜单等
  - **iframe:** 单独为 iframe 列一个分类

在框架的支持下，大部分底层细节都已封装好，编写测试的过程将更关注业务逻辑本身。

