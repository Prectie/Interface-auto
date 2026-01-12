
        function _base64ToArrayBuffer(base64) {
            var binary_string = window.atob(base64);
            var len = binary_string.length;
            var bytes = new Uint8Array(len);
            for (var i = 0; i < len; i++) {
                bytes[i] = binary_string.charCodeAt(i);
            }
            return bytes.buffer;
        }

        function _arrayBufferToBase64( buffer ) {
          var binary = '';
          var bytes = new Uint8Array( buffer );
          var len = bytes.byteLength;
          for (var i = 0; i < len; i++) {
             binary += String.fromCharCode( bytes[ i ] );
          }
          return window.btoa( binary );
        }

        document.addEventListener("DOMContentLoaded", function() {
            var old_prefilter = jQuery.htmlPrefilter;

            jQuery.htmlPrefilter = function(v) {
            
                var regs = [
                    /<a[^>]*href="(?<url>[^"]*)"[^>]*>/gi,
                    /<img[^>]*src="(?<url>[^"]*)"\/?>/gi,
                    /<source[^>]*src="(?<url>[^"]*)"/gi
                ];
                
                var replaces = {};

                for (i in regs)
                {
                    reg = regs[i];

                    var m = true;
                    var n = 0;
                    while (m && n < 100)
                    {
                        n += 1;
                        
                        m = reg.exec(v);
                        if (m)
                        {
                            if (m['groups'] && m['groups']['url'])
                            {
                                var url = m['groups']['url'];
                                if (server_data.hasOwnProperty(url))
                                {
                                    console.log(`Added url:${url} to be replaced with data of ${server_data[url].length} bytes length`);
                                    replaces[url] = server_data[url];                                    
                                }
                            }
                        }
                    }
                }
                
                for (let src in replaces)
                {
                    let dest = replaces[src];
                    v = v.replace(src, dest);
                }

                return old_prefilter(v);
            };
        });

        var server_data={
 "data/behaviors.csv": "\"Epic\",\"Feature\",\"Story\",\"FAILED\",\"BROKEN\",\"PASSED\",\"SKIPPED\",\"UNKNOWN\"\n\"\",\"登录模块\",\"登录功能\",\"0\",\"0\",\"1\",\"0\",\"0\"\n", 
 "data/behaviors.json": "{\n  \"uid\" : \"b1a8273437954620fa374b796ffaacdd\",\n  \"name\" : \"behaviors\",\n  \"children\" : [ {\n    \"name\" : \"登录模块\",\n    \"children\" : [ {\n      \"name\" : \"登录功能\",\n      \"children\" : [ {\n        \"name\" : \"登录用例标题\",\n        \"uid\" : \"104199f2060d4dfb\",\n        \"parentUid\" : \"77c8e60e806ab67bbe72b562bb863572\",\n        \"status\" : \"passed\",\n        \"time\" : {\n          \"start\" : 1762518932893,\n          \"stop\" : 1762519430379,\n          \"duration\" : 497486\n        },\n        \"flaky\" : false,\n        \"newFailed\" : false,\n        \"parameters\" : [ \"''\" ]\n      } ],\n      \"uid\" : \"77c8e60e806ab67bbe72b562bb863572\"\n    } ],\n    \"uid\" : \"6958045a481574bf02bb11ef07a7047b\"\n  } ]\n}", 
 "data/categories.csv": "", 
 "data/categories.json": "{\n  \"uid\" : \"4b4757e66a1912dae1a509f688f20b0f\",\n  \"name\" : \"categories\",\n  \"children\" : [ ]\n}", 
 "data/packages.json": "{\n  \"uid\" : \"83edc06c07f9ae9e47eb6dd1b683e4e2\",\n  \"name\" : \"packages\",\n  \"children\" : [ {\n    \"name\" : \"HAT.core.TestRunner\",\n    \"children\" : [ {\n      \"name\" : \"登录用例标题\",\n      \"uid\" : \"104199f2060d4dfb\",\n      \"parentUid\" : \"4f49bfd95b07058304187c1f573400fa\",\n      \"status\" : \"passed\",\n      \"time\" : {\n        \"start\" : 1762518932893,\n        \"stop\" : 1762519430379,\n        \"duration\" : 497486\n      },\n      \"flaky\" : false,\n      \"newFailed\" : false,\n      \"parameters\" : [ \"''\" ]\n    } ],\n    \"uid\" : \"HAT.core.TestRunner\"\n  } ]\n}", 
 "data/suites.csv": "\"Status\",\"Start Time\",\"Stop Time\",\"Duration in ms\",\"Parent Suite\",\"Suite\",\"Sub Suite\",\"Test Class\",\"Test Method\",\"Name\",\"Description\"\n\"passed\",\"Fri Nov 07 20:35:32 CST 2025\",\"Fri Nov 07 20:43:50 CST 2025\",\"497486\",\"HAT.core\",\"TestRunner\",\"TestRunner\",\"\",\"\",\"登录用例标题\",\"\"\n", 
 "data/suites.json": "{\n  \"uid\" : \"98d3104e051c652961429bf95fa0b5d6\",\n  \"name\" : \"suites\",\n  \"children\" : [ {\n    \"name\" : \"HAT.core\",\n    \"children\" : [ {\n      \"name\" : \"TestRunner\",\n      \"children\" : [ {\n        \"name\" : \"TestRunner\",\n        \"children\" : [ {\n          \"name\" : \"登录用例标题\",\n          \"uid\" : \"104199f2060d4dfb\",\n          \"parentUid\" : \"2db32f78fe84d9e9d139df1148bfcdbc\",\n          \"status\" : \"passed\",\n          \"time\" : {\n            \"start\" : 1762518932893,\n            \"stop\" : 1762519430379,\n            \"duration\" : 497486\n          },\n          \"flaky\" : false,\n          \"newFailed\" : false,\n          \"parameters\" : [ \"''\" ]\n        } ],\n        \"uid\" : \"2db32f78fe84d9e9d139df1148bfcdbc\"\n      } ],\n      \"uid\" : \"86885bbc367980c89add99d01eda23a9\"\n    } ],\n    \"uid\" : \"6ba8b2b0c2a613f1452d6eddd6594146\"\n  } ]\n}", 
 "data/timeline.json": "{\n  \"uid\" : \"ab17fc5a4eb3bca4b216b548c7f9fcbc\",\n  \"name\" : \"timeline\",\n  \"children\" : [ {\n    \"name\" : \"DESKTOP-DIQC85V\",\n    \"children\" : [ {\n      \"name\" : \"9916-MainThread\",\n      \"children\" : [ {\n        \"name\" : \"登录用例标题\",\n        \"uid\" : \"104199f2060d4dfb\",\n        \"parentUid\" : \"c642164233014fa52a92e2ccd50ba6be\",\n        \"status\" : \"passed\",\n        \"time\" : {\n          \"start\" : 1762518932893,\n          \"stop\" : 1762519430379,\n          \"duration\" : 497486\n        },\n        \"flaky\" : false,\n        \"newFailed\" : false,\n        \"parameters\" : [ \"''\" ]\n      } ],\n      \"uid\" : \"c642164233014fa52a92e2ccd50ba6be\"\n    } ],\n    \"uid\" : \"8e73d0a1016dc2454738fb71bf0c593a\"\n  } ]\n}", 
 "data/attachments/47e3c4aa4a9be888.txt": "\n开始执行:   0%|          | 0/1 [00:00&lt;?, ?it/s]\n登录用例标题-当前步骤:发送登录接口:   0%|          | 0/1 [00:03&lt;?, ?it/s]\n登录用例标题-当前步骤:发送登录接口: 100%|██████████| 1/1 [00:04&lt;00:00,  4.38s/it]\n登录用例标题-当前步骤:发送登录接口: 100%|██████████| 1/1 [01:54&lt;00:00, 114.79s/it]\n", 
 "data/attachments/945b35d84cd7cf0f.txt": "没有渲染前的字典值数据 {'操作类型': '发送请求POST', '请求地址': '{{URL}}', 'URL参数': {'s': '/api/user/login', 'application': 'app', 'application_client_type': 'weixin'}, '请求数据': {'accounts': '{{uname}}', 'pwd': '123456', 'type': 'username'}}\n渲染后的字典值数据 {'操作类型': '发送请求POST', '请求地址': 'http://shop-xo.hctestedu.com', 'URL参数': {'s': '/api/user/login', 'application': 'app', 'application_client_type': 'weixin'}, '请求数据': {'accounts': 'youer', 'pwd': '123456', 'type': 'username'}}\n登陆响应数据 {'msg': '登录成功', 'code': 0, 'data': {'id': '247', 'username': 'youer', 'nickname': '', 'mobile': '', 'email': '', 'avatar': 'http://shop-xo.hctestedu.com/static/index/default/images/default-user-avatar.jpg', 'alipay_openid': '', 'weixin_openid': '', 'weixin_unionid': '', 'weixin_web_openid': '', 'baidu_openid': '', 'toutiao_openid': '', 'qq_openid': '', 'qq_unionid': '', 'integral': '0', 'locking_integral': '0', 'referrer': '0', 'add_time': '1751111586', 'add_time_text': '2025-06-28 19:53:06', 'mobile_security': '', 'email_security': '', 'user_name_view': 'youer', 'is_mandatory_bind_mobile': 0, 'token': '33b5780bd75c8160691acd4fe926bae5'}}\n后置脚本\n", 
 "data/test-cases/104199f2060d4dfb.json": "{\n  \"uid\" : \"104199f2060d4dfb\",\n  \"name\" : \"登录用例标题\",\n  \"fullName\" : \"HAT.core.TestRunner.TestRunner#test_case_execute\",\n  \"historyId\" : \"a554c10c8300ec0771841d6b0e3dda4e\",\n  \"time\" : {\n    \"start\" : 1762518932893,\n    \"stop\" : 1762519430379,\n    \"duration\" : 497486\n  },\n  \"status\" : \"passed\",\n  \"flaky\" : false,\n  \"newFailed\" : false,\n  \"beforeStages\" : [ ],\n  \"testStage\" : {\n    \"status\" : \"passed\",\n    \"steps\" : [ {\n      \"name\" : \"发送登录接口\",\n      \"time\" : {\n        \"start\" : 1762519273769,\n        \"stop\" : 1762519381618,\n        \"duration\" : 107849\n      },\n      \"status\" : \"passed\",\n      \"steps\" : [ {\n        \"name\" : \"发送请求POST\",\n        \"time\" : {\n          \"start\" : 1762519370293,\n          \"stop\" : 1762519381617,\n          \"duration\" : 11324\n        },\n        \"status\" : \"passed\",\n        \"steps\" : [ ],\n        \"attachments\" : [ ],\n        \"parameters\" : [ {\n          \"name\" : \"操作类型\",\n          \"value\" : \"'发送请求POST'\"\n        }, {\n          \"name\" : \"请求地址\",\n          \"value\" : \"'http://shop-xo.hctestedu.com'\"\n        }, {\n          \"name\" : \"URL参数\",\n          \"value\" : \"{'s': '/api/user/login', 'application': 'app', 'application_client_type': 'weixin'}\"\n        }, {\n          \"name\" : \"请求数据\",\n          \"value\" : \"{'accounts': 'youer', 'pwd': '123456', 'type': 'username'}\"\n        } ],\n        \"stepsCount\" : 0,\n        \"hasContent\" : true,\n        \"attachmentsCount\" : 0,\n        \"shouldDisplayMessage\" : false\n      } ],\n      \"attachments\" : [ ],\n      \"parameters\" : [ ],\n      \"stepsCount\" : 1,\n      \"hasContent\" : true,\n      \"attachmentsCount\" : 0,\n      \"shouldDisplayMessage\" : false\n    } ],\n    \"attachments\" : [ {\n      \"uid\" : \"945b35d84cd7cf0f\",\n      \"name\" : \"stdout\",\n      \"source\" : \"945b35d84cd7cf0f.txt\",\n      \"type\" : \"text/plain\",\n      \"size\" : 1250\n    }, {\n      \"uid\" : \"47e3c4aa4a9be888\",\n      \"name\" : \"stderr\",\n      \"source\" : \"47e3c4aa4a9be888.txt\",\n      \"type\" : \"text/plain\",\n      \"size\" : 380\n    } ],\n    \"parameters\" : [ ],\n    \"stepsCount\" : 2,\n    \"hasContent\" : true,\n    \"attachmentsCount\" : 2,\n    \"shouldDisplayMessage\" : false\n  },\n  \"afterStages\" : [ ],\n  \"labels\" : [ {\n    \"name\" : \"feature\",\n    \"value\" : \"登录模块\"\n  }, {\n    \"name\" : \"story\",\n    \"value\" : \"登录功能\"\n  }, {\n    \"name\" : \"parentSuite\",\n    \"value\" : \"HAT.core\"\n  }, {\n    \"name\" : \"suite\",\n    \"value\" : \"TestRunner\"\n  }, {\n    \"name\" : \"subSuite\",\n    \"value\" : \"TestRunner\"\n  }, {\n    \"name\" : \"host\",\n    \"value\" : \"DESKTOP-DIQC85V\"\n  }, {\n    \"name\" : \"thread\",\n    \"value\" : \"9916-MainThread\"\n  }, {\n    \"name\" : \"framework\",\n    \"value\" : \"pytest\"\n  }, {\n    \"name\" : \"language\",\n    \"value\" : \"cpython3\"\n  }, {\n    \"name\" : \"package\",\n    \"value\" : \"HAT.core.TestRunner\"\n  }, {\n    \"name\" : \"resultFormat\",\n    \"value\" : \"allure2\"\n  } ],\n  \"parameters\" : [ {\n    \"name\" : \"caseinfo\",\n    \"value\" : \"''\"\n  } ],\n  \"links\" : [ ],\n  \"hidden\" : false,\n  \"retry\" : false,\n  \"extra\" : {\n    \"severity\" : \"normal\",\n    \"retries\" : [ ],\n    \"categories\" : [ ],\n    \"tags\" : [ ]\n  },\n  \"source\" : \"104199f2060d4dfb.json\",\n  \"parameterValues\" : [ \"''\" ]\n}", 
 "export/influxDbData.txt": "launch_status failed=0 1762519433000000000\nlaunch_status broken=0 1762519433000000000\nlaunch_status passed=1 1762519433000000000\nlaunch_status skipped=0 1762519433000000000\nlaunch_status unknown=0 1762519433000000000\nlaunch_time duration=497486 1762519433000000000\nlaunch_time min_duration=497486 1762519433000000000\nlaunch_time max_duration=497486 1762519433000000000\nlaunch_time sum_duration=497486 1762519433000000000\nlaunch_retries retries=0 1762519433000000000\nlaunch_retries run=1 1762519433000000000\n", 
 "export/mail.html": "data:text/html;base64, PCFET0NUWVBFIGh0bWw+CjxodG1sPgo8aGVhZD4KICAgIDxtZXRhIGNoYXJzZXQ9InV0Zi04Ij4KICAgIDx0aXRsZT5BbGx1cmUgUmVwb3J0IHN1bW1hcnkgbWFpbDwvdGl0bGU+CjwvaGVhZD4KPGJvZHk+CiAgICBNYWlsIGJvZHkKPC9ib2R5Pgo8L2h0bWw+Cg==", 
 "export/prometheusData.txt": "launch_status_failed 0\nlaunch_status_broken 0\nlaunch_status_passed 1\nlaunch_status_skipped 0\nlaunch_status_unknown 0\nlaunch_time_duration 497486\nlaunch_time_min_duration 497486\nlaunch_time_max_duration 497486\nlaunch_time_sum_duration 497486\nlaunch_retries_retries 0\nlaunch_retries_run 1\n", 
 "history/categories-trend.json": "[ {\n  \"data\" : { }\n} ]", 
 "history/duration-trend.json": "[ {\n  \"data\" : {\n    \"duration\" : 497486\n  }\n} ]", 
 "history/history-trend.json": "[ {\n  \"data\" : {\n    \"failed\" : 0,\n    \"broken\" : 0,\n    \"skipped\" : 0,\n    \"passed\" : 1,\n    \"unknown\" : 0,\n    \"total\" : 1\n  }\n} ]", 
 "history/history.json": "{\n  \"a554c10c8300ec0771841d6b0e3dda4e\" : {\n    \"statistic\" : {\n      \"failed\" : 0,\n      \"broken\" : 0,\n      \"skipped\" : 0,\n      \"passed\" : 1,\n      \"unknown\" : 0,\n      \"total\" : 1\n    },\n    \"items\" : [ {\n      \"uid\" : \"104199f2060d4dfb\",\n      \"status\" : \"passed\",\n      \"time\" : {\n        \"start\" : 1762518932893,\n        \"stop\" : 1762519430379,\n        \"duration\" : 497486\n      }\n    } ]\n  }\n}", 
 "history/retry-trend.json": "[ {\n  \"data\" : {\n    \"run\" : 1,\n    \"retry\" : 0\n  }\n} ]", 
 "plugins/behaviors/index.js": "'use strict';\n\nallure.api.addTranslation('en', {\n    tab: {\n        behaviors: {\n            name: 'Behaviors'\n        }\n    },\n    widget: {\n        behaviors: {\n            name: 'Features by stories',\n            showAll: 'show all'\n        }\n    }\n});\n\nallure.api.addTranslation('ru', {\n    tab: {\n        behaviors: {\n            name: 'Функциональность'\n        }\n    },\n    widget: {\n        behaviors: {\n            name: 'Функциональность',\n            showAll: 'показать все'\n        }\n    }\n});\n\nallure.api.addTranslation('zh', {\n    tab: {\n        behaviors: {\n            name: '功能'\n        }\n    },\n    widget: {\n        behaviors: {\n            name: '特性场景',\n            showAll: '显示所有'\n        }\n    }\n});\n\nallure.api.addTranslation('de', {\n    tab: {\n        behaviors: {\n            name: 'Verhalten'\n        }\n    },\n    widget: {\n        behaviors: {\n            name: 'Features nach Stories',\n            showAll: 'Zeige alle'\n        }\n    }\n});\n\nallure.api.addTranslation('he', {\n    tab: {\n        behaviors: {\n            name: 'התנהגויות'\n        }\n    },\n    widget: {\n        behaviors: {\n            name: 'תכונות לפי סיפורי משתמש',\n            showAll: 'הצג הכול'\n        }\n    }\n});\n\nallure.api.addTranslation('br', {\n    tab: {\n        behaviors: {\n            name: 'Comportamentos'\n        }\n    }, \n    widget: {\n        behaviors: {\n            name: 'Funcionalidades por história', \n            showAll: 'Mostrar tudo'\n        }\n    }\n});\n\nallure.api.addTranslation('ja', {\n    tab: {\n        behaviors: {\n            name: '振る舞い'\n        }\n    },\n    widget: {\n        behaviors: {\n            name: 'ストーリー別の機能',\n            showAll: '全て表示'\n        }\n    }\n});\n\nallure.api.addTranslation('es', {\n    tab: {\n        behaviors: {\n            name: 'Funcionalidades'\n        }\n    },\n    widget: {\n        behaviors: {\n            name: 'Funcionalidades por Historias de Usuario',\n            showAll: 'mostrar todo'\n        }\n    }\n});\n\nallure.api.addTranslation('kr', {\n    tab: {\n        behaviors: {\n            name: '동작'\n        }\n    },\n    widget: {\n        behaviors: {\n            name: '스토리별 기능',\n            showAll: '전체 보기'\n        }\n    }\n});\n\nallure.api.addTab('behaviors', {\n    title: 'tab.behaviors.name', icon: 'fa fa-list',\n    route: 'behaviors(/)(:testGroup)(/)(:testResult)(/)(:testResultTab)(/)',\n    onEnter: (function (testGroup, testResult, testResultTab) {\n        return new allure.components.TreeLayout({\n            testGroup: testGroup,\n            testResult: testResult,\n            testResultTab: testResultTab,\n            tabName: 'tab.behaviors.name',\n            baseUrl: 'behaviors',\n            url: 'data/behaviors.json',\n            csvUrl: 'data/behaviors.csv'\n        });\n    })\n});\n\nallure.api.addWidget('widgets', 'behaviors', allure.components.WidgetStatusView.extend({\n    rowTag: 'a',\n    title: 'widget.behaviors.name',\n    baseUrl: 'behaviors',\n    showLinks: true\n}));", 
 "plugins/packages/index.js": "'use strict';\n\nallure.api.addTranslation('en', {\n    tab: {\n        packages: {\n            name: 'Packages'\n        }\n    }\n});\n\nallure.api.addTranslation('ru', {\n    tab: {\n        packages: {\n            name: 'Пакеты'\n        }\n    }\n});\n\nallure.api.addTranslation('zh', {\n    tab: {\n        packages: {\n            name: '包'\n        }\n    }\n});\n\nallure.api.addTranslation('de', {\n    tab: {\n        packages: {\n            name: 'Pakete'\n        }\n    }\n});\n\nallure.api.addTranslation('he', {\n    tab: {\n        packages: {\n            name: 'חבילות'\n        }\n    }\n});\n\nallure.api.addTranslation('br', {\n    tab: {\n        packages: {\n            name: 'Pacotes'\n        }\n    }\n});\n\nallure.api.addTranslation('ja', {\n    tab: {\n        packages: {\n            name: 'パッケージ'\n        }\n    }\n});\n\nallure.api.addTranslation('es', {\n    tab: {\n        packages: {\n            name: 'Paquetes'\n        }\n    }\n});\n\nallure.api.addTranslation('kr', {\n    tab: {\n        packages: {\n            name: '패키지'\n        }\n    }\n});\n\nallure.api.addTab('packages', {\n    title: 'tab.packages.name', icon: 'fa fa-align-left',\n    route: 'packages(/)(:testGroup)(/)(:testResult)(/)(:testResultTab)(/)',\n    onEnter: (function (testGroup, testResult, testResultTab) {\n        return new allure.components.TreeLayout({\n            testGroup: testGroup,\n            testResult: testResult,\n            testResultTab: testResultTab,\n            tabName: 'tab.packages.name',\n            baseUrl: 'packages',\n            url: 'data/packages.json'\n        });\n    })\n});\n", 
 "plugins/screen-diff/index.js": "(function () {\n    var settings = allure.getPluginSettings('screen-diff', {diffType: 'diff'});\n\n    function renderImage(src) {\n        return '&lt;div class=\"screen-diff__container\"&gt;' +\n            '&lt;img class=\"screen-diff__image\" src=\"data/attachments/' + src + '\"&gt;' +\n            '&lt;/div&gt;';\n    }\n\n    function renderDiffContent(type, data) {\n        function findImage(name) {\n            if (data.testStage && data.testStage.attachments) {\n                return data.testStage.attachments.filter(function (attachment) {\n                    return attachment.name === name;\n                })[0];\n            }\n            return null;\n        }\n\n        var diffImage = findImage('diff');\n        var actualImage = findImage('actual');\n        var expectedImage = findImage('expected');\n\n        if (!diffImage && !actualImage && !expectedImage) {\n            return '&lt;span&gt;Diff, actual and expected image have not been provided.&lt;/span&gt;';\n        }\n\n        if (type === 'diff') {\n            if (!diffImage) {\n                return renderImage(actualImage.source);\n            }\n            return renderImage(diffImage.source);\n        }\n        if (type === 'overlay') {\n            return '&lt;div class=\"screen-diff__overlay screen-diff__container\"&gt;' +\n                '&lt;img class=\"screen-diff__image\" src=\"data/attachments/' + expectedImage.source + '\"&gt;' +\n                '&lt;div class=\"screen-diff__image-over\"&gt;' +\n                '&lt;img class=\"screen-diff__image\" src=\"data/attachments/' + actualImage.source + '\"&gt;' +\n                '&lt;/div&gt;' +\n                '&lt;/div&gt;';\n        }\n    }\n\n    var ScreenDiffView = Backbone.Marionette.View.extend({\n        className: 'pane__section',\n        events: {\n            'click [name=\"screen-diff-type\"]': 'onDiffTypeChange',\n            'mousemove .screen-diff__overlay': 'onOverlayMove'\n        },\n        templateContext: function () {\n            return {\n                diffType: settings.get('diffType')\n            }\n        },\n        template: function (data) {\n            var testType = data.labels.filter(function (label) {\n                return label.name === 'testType'\n            })[0];\n\n            if (!testType || testType.value !== 'screenshotDiff') {\n                return '';\n            }\n\n            return '&lt;h3 class=\"pane__section-title\"&gt;Screen Diff&lt;/h3&gt;' +\n                '&lt;div class=\"screen-diff__content\"&gt;' +\n                '&lt;div class=\"screen-diff__switchers\"&gt;' +\n                '&lt;label&gt;&lt;input type=\"radio\" name=\"screen-diff-type\" value=\"diff\"&gt; Show diff&lt;/label&gt;' +\n                '&lt;label&gt;&lt;input type=\"radio\" name=\"screen-diff-type\" value=\"overlay\"&gt; Show overlay&lt;/label&gt;' +\n                '&lt;/div&gt;' +\n                renderDiffContent(data.diffType, data) +\n                '&lt;/div&gt;';\n        },\n        adjustImageSize: function (event) {\n            var overImage = this.$(event.target);\n            overImage.width(overImage.width());\n        },\n        onRender: function () {\n            const diffType = settings.get('diffType');\n            this.$('[name=\"screen-diff-type\"][value=\"' + diffType + '\"]').prop('checked', true);\n            if (diffType === 'overlay') {\n                this.$('.screen-diff__image-over img').on('load', this.adjustImageSize.bind(this));\n            }\n        },\n        onOverlayMove: function (event) {\n            var pageX = event.pageX;\n            var containerScroll = this.$('.screen-diff__container').scrollLeft();\n            var elementX = event.currentTarget.getBoundingClientRect().left;\n            var delta = pageX - elementX + containerScroll;\n            this.$('.screen-diff__image-over').width(delta);\n        },\n        onDiffTypeChange: function (event) {\n            settings.save('diffType', event.target.value);\n            this.render();\n        }\n    });\n    allure.api.addTestResultBlock(ScreenDiffView, {position: 'before'});\n})();\n", 
 "plugins/screen-diff/styles.css": ".screen-diff__switchers {\n  margin-bottom: 1em;\n}\n\n.screen-diff__switchers label + label {\n  margin-left: 1em;\n}\n\n.screen-diff__overlay {\n  position: relative;\n  cursor: col-resize;\n}\n\n.screen-diff__container {\n  overflow-x: auto;\n}\n\n.screen-diff__image-over {\n  top: 0;\n  left: 0;\n  bottom: 0;\n  background: #fff;\n  position: absolute;\n  overflow: hidden;\n  box-shadow: 2px 0 1px -1px #aaa;\n}\n", 
 "widgets/behaviors.json": "{\n  \"total\" : 1,\n  \"items\" : [ {\n    \"uid\" : \"6958045a481574bf02bb11ef07a7047b\",\n    \"name\" : \"登录模块\",\n    \"statistic\" : {\n      \"failed\" : 0,\n      \"broken\" : 0,\n      \"skipped\" : 0,\n      \"passed\" : 1,\n      \"unknown\" : 0,\n      \"total\" : 1\n    }\n  } ]\n}", 
 "widgets/categories-trend.json": "[ {\n  \"data\" : { }\n} ]", 
 "widgets/categories.json": "{\n  \"total\" : 0,\n  \"items\" : [ ]\n}", 
 "widgets/duration-trend.json": "[ {\n  \"data\" : {\n    \"duration\" : 497486\n  }\n} ]", 
 "widgets/duration.json": "[ {\n  \"uid\" : \"104199f2060d4dfb\",\n  \"name\" : \"登录用例标题\",\n  \"time\" : {\n    \"start\" : 1762518932893,\n    \"stop\" : 1762519430379,\n    \"duration\" : 497486\n  },\n  \"status\" : \"passed\",\n  \"severity\" : \"normal\"\n} ]", 
 "widgets/environment.json": "[ ]", 
 "widgets/executors.json": "[ ]", 
 "widgets/history-trend.json": "[ {\n  \"data\" : {\n    \"failed\" : 0,\n    \"broken\" : 0,\n    \"skipped\" : 0,\n    \"passed\" : 1,\n    \"unknown\" : 0,\n    \"total\" : 1\n  }\n} ]", 
 "widgets/launch.json": "[ ]", 
 "widgets/retry-trend.json": "[ {\n  \"data\" : {\n    \"run\" : 1,\n    \"retry\" : 0\n  }\n} ]", 
 "widgets/severity.json": "[ {\n  \"uid\" : \"104199f2060d4dfb\",\n  \"name\" : \"登录用例标题\",\n  \"time\" : {\n    \"start\" : 1762518932893,\n    \"stop\" : 1762519430379,\n    \"duration\" : 497486\n  },\n  \"status\" : \"passed\",\n  \"severity\" : \"normal\"\n} ]", 
 "widgets/status-chart.json": "[ {\n  \"uid\" : \"104199f2060d4dfb\",\n  \"name\" : \"登录用例标题\",\n  \"time\" : {\n    \"start\" : 1762518932893,\n    \"stop\" : 1762519430379,\n    \"duration\" : 497486\n  },\n  \"status\" : \"passed\",\n  \"severity\" : \"normal\"\n} ]", 
 "widgets/suites.json": "{\n  \"total\" : 1,\n  \"items\" : [ {\n    \"uid\" : \"6ba8b2b0c2a613f1452d6eddd6594146\",\n    \"name\" : \"HAT.core\",\n    \"statistic\" : {\n      \"failed\" : 0,\n      \"broken\" : 0,\n      \"skipped\" : 0,\n      \"passed\" : 1,\n      \"unknown\" : 0,\n      \"total\" : 1\n    }\n  } ]\n}", 
 "widgets/summary.json": "{\n  \"reportName\" : \"Allure Report\",\n  \"testRuns\" : [ ],\n  \"statistic\" : {\n    \"failed\" : 0,\n    \"broken\" : 0,\n    \"skipped\" : 0,\n    \"passed\" : 1,\n    \"unknown\" : 0,\n    \"total\" : 1\n  },\n  \"time\" : {\n    \"start\" : 1762518932893,\n    \"stop\" : 1762519430379,\n    \"duration\" : 497486,\n    \"minDuration\" : 497486,\n    \"maxDuration\" : 497486,\n    \"sumDuration\" : 497486\n  }\n}", 
};
    var server = sinon.fakeServer.create();

                server.respondWith("GET", "data/behaviors.csv", [
                      200, { "Content-Type": "text/csv" }, server_data["data/behaviors.csv"],
                ]);
            
                server.respondWith("GET", "data/behaviors.json", [
                      200, { "Content-Type": "application/json" }, server_data["data/behaviors.json"],
                ]);
            
                server.respondWith("GET", "data/categories.csv", [
                      200, { "Content-Type": "text/csv" }, server_data["data/categories.csv"],
                ]);
            
                server.respondWith("GET", "data/categories.json", [
                      200, { "Content-Type": "application/json" }, server_data["data/categories.json"],
                ]);
            
                server.respondWith("GET", "data/packages.json", [
                      200, { "Content-Type": "application/json" }, server_data["data/packages.json"],
                ]);
            
                server.respondWith("GET", "data/suites.csv", [
                      200, { "Content-Type": "text/csv" }, server_data["data/suites.csv"],
                ]);
            
                server.respondWith("GET", "data/suites.json", [
                      200, { "Content-Type": "application/json" }, server_data["data/suites.json"],
                ]);
            
                server.respondWith("GET", "data/timeline.json", [
                      200, { "Content-Type": "application/json" }, server_data["data/timeline.json"],
                ]);
            
                server.respondWith("GET", "data/attachments/47e3c4aa4a9be888.txt", [
                      200, { "Content-Type": "text/plain;charset=UTF-8" }, server_data["data/attachments/47e3c4aa4a9be888.txt"],
                ]);
            
                server.respondWith("GET", "data/attachments/945b35d84cd7cf0f.txt", [
                      200, { "Content-Type": "text/plain;charset=UTF-8" }, server_data["data/attachments/945b35d84cd7cf0f.txt"],
                ]);
            
                server.respondWith("GET", "data/test-cases/104199f2060d4dfb.json", [
                      200, { "Content-Type": "application/json" }, server_data["data/test-cases/104199f2060d4dfb.json"],
                ]);
            
                server.respondWith("GET", "export/influxDbData.txt", [
                      200, { "Content-Type": "text/plain;charset=UTF-8" }, server_data["export/influxDbData.txt"],
                ]);
            
                server.respondWith("GET", "export/mail.html", [
                      200, { "Content-Type": "text/html" }, server_data["export/mail.html"],
                ]);
            
                server.respondWith("GET", "export/prometheusData.txt", [
                      200, { "Content-Type": "text/plain;charset=UTF-8" }, server_data["export/prometheusData.txt"],
                ]);
            
                server.respondWith("GET", "history/categories-trend.json", [
                      200, { "Content-Type": "application/json" }, server_data["history/categories-trend.json"],
                ]);
            
                server.respondWith("GET", "history/duration-trend.json", [
                      200, { "Content-Type": "application/json" }, server_data["history/duration-trend.json"],
                ]);
            
                server.respondWith("GET", "history/history-trend.json", [
                      200, { "Content-Type": "application/json" }, server_data["history/history-trend.json"],
                ]);
            
                server.respondWith("GET", "history/history.json", [
                      200, { "Content-Type": "application/json" }, server_data["history/history.json"],
                ]);
            
                server.respondWith("GET", "history/retry-trend.json", [
                      200, { "Content-Type": "application/json" }, server_data["history/retry-trend.json"],
                ]);
            
                server.respondWith("GET", "plugins/behaviors/index.js", [
                      200, { "Content-Type": "application/javascript" }, server_data["plugins/behaviors/index.js"],
                ]);
            
                server.respondWith("GET", "plugins/packages/index.js", [
                      200, { "Content-Type": "application/javascript" }, server_data["plugins/packages/index.js"],
                ]);
            
                server.respondWith("GET", "plugins/screen-diff/index.js", [
                      200, { "Content-Type": "application/javascript" }, server_data["plugins/screen-diff/index.js"],
                ]);
            
                server.respondWith("GET", "plugins/screen-diff/styles.css", [
                      200, { "Content-Type": "text/css" }, server_data["plugins/screen-diff/styles.css"],
                ]);
            
                server.respondWith("GET", "widgets/behaviors.json", [
                      200, { "Content-Type": "application/json" }, server_data["widgets/behaviors.json"],
                ]);
            
                server.respondWith("GET", "widgets/categories-trend.json", [
                      200, { "Content-Type": "application/json" }, server_data["widgets/categories-trend.json"],
                ]);
            
                server.respondWith("GET", "widgets/categories.json", [
                      200, { "Content-Type": "application/json" }, server_data["widgets/categories.json"],
                ]);
            
                server.respondWith("GET", "widgets/duration-trend.json", [
                      200, { "Content-Type": "application/json" }, server_data["widgets/duration-trend.json"],
                ]);
            
                server.respondWith("GET", "widgets/duration.json", [
                      200, { "Content-Type": "application/json" }, server_data["widgets/duration.json"],
                ]);
            
                server.respondWith("GET", "widgets/environment.json", [
                      200, { "Content-Type": "application/json" }, server_data["widgets/environment.json"],
                ]);
            
                server.respondWith("GET", "widgets/executors.json", [
                      200, { "Content-Type": "application/json" }, server_data["widgets/executors.json"],
                ]);
            
                server.respondWith("GET", "widgets/history-trend.json", [
                      200, { "Content-Type": "application/json" }, server_data["widgets/history-trend.json"],
                ]);
            
                server.respondWith("GET", "widgets/launch.json", [
                      200, { "Content-Type": "application/json" }, server_data["widgets/launch.json"],
                ]);
            
                server.respondWith("GET", "widgets/retry-trend.json", [
                      200, { "Content-Type": "application/json" }, server_data["widgets/retry-trend.json"],
                ]);
            
                server.respondWith("GET", "widgets/severity.json", [
                      200, { "Content-Type": "application/json" }, server_data["widgets/severity.json"],
                ]);
            
                server.respondWith("GET", "widgets/status-chart.json", [
                      200, { "Content-Type": "application/json" }, server_data["widgets/status-chart.json"],
                ]);
            
                server.respondWith("GET", "widgets/suites.json", [
                      200, { "Content-Type": "application/json" }, server_data["widgets/suites.json"],
                ]);
            
                server.respondWith("GET", "widgets/summary.json", [
                      200, { "Content-Type": "application/json" }, server_data["widgets/summary.json"],
                ]);
            server.autoRespond = true;