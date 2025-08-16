import os
import io
import re
import random
import pygame
import asyncio
import threading
import tkinter as tk
from time import sleep
from queue import Queue
from openai import OpenAI
from tkinter import PhotoImage
from edge_tts import Communicate, VoicesManager

# 设置语音播报类
class TextToSpeech:
    def __init__(self):
        # 重设玩家音色和相关语速加快
        self.ids = [6, 3, 4, 5, 7, 8, 9, 10, 11, 13]
        self.rate = ["+20%", "+45%", "+45%", "+45%", "+45%", "+45%", "+50%", "+50%", "+50%", "+60%"]
        # 首先执行语音获取，仅执行一次
        asyncio.run(self.get_voices())

    async def get_voices(self):
        # 获取全部中文语音
        self.voices = await VoicesManager.create()
        self.chinese_voices = self.voices.find(Language="zh")

    async def speak(self, text, id = 0, timeout = 30):
        # 根据 id 选用不同音色播报，默认为0，即上帝。
        voice = self.chinese_voices[self.ids[id]]["ShortName"]
        # 创建Communicate对象并获取音频流
        communicate = Communicate(text, voice=voice, rate = self.rate[id])
        # 将音频数据存入内存（不保存为文件）
        audio_stream = io.BytesIO()
        try:
            # 封装 async for 循环成一个可等待的协程
            async def collect_audio():
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_stream.write(chunk["data"])

            # 使用 asyncio.wait_for 限制总时间
            await asyncio.wait_for(collect_audio(), timeout=timeout)
        except asyncio.TimeoutError:
            print(f"语音生成超过 {timeout} 秒，已终止")
            return
        except Exception as e:
            print(f"语音生成出错: {e}")
            return

        # 重置指针并播放
        audio_stream.seek(0)
        pygame.mixer.music.load(audio_stream)
        pygame.mixer.music.play()

        # 等待播放完成
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)

# 设置大模型智能体类
class Agents:
    def __init__(self, api_key, base_url, model, role_prompt):
        # 传入 API URL model 和基本设置
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.role_prompt = role_prompt
        self.history = [{"role": "system", "content": role_prompt}]
        self.model = model

    # 定义 tell 函数，仅单方面告知不对话
    def tell(self, query):
        self.history.append({"role": "user", "content": query})

    # 定义 chat 函数，根据指令和历史全部信息进行对话
    def chat(self, query):
        self.history.append({"role": "user", "content": query})
        response = self.client.chat.completions.create(
            model=self.model,
            messages= self.history,
            temperature=0.9,
            stream=False,
        )
        answer = response.choices[0].message.content
        # 所有历史对话信息存入 self.history
        self.history.append({"role": "assistant","content": answer})
        return answer

# 定义AI狼人杀类
class WerewolfGame:
    def __init__(self):
        # tkinter UI 界面基本设置
        self.root = tk.Tk()
        self.root.title("AI狼人杀锦标赛")
        self.root.geometry("723x963")
        # 为执行游戏界面切换，所有控件置于 self.current_frame 之下
        self.current_frame = None
        # 调用语音播报类，完成语音获取
        self.voice = TextToSpeech()
        self.setup_main_menu()

    # 清除 self.current_frame 实现 UI 界面的伪更新
    def clear_frame(self):
        if self.current_frame:
            self.current_frame.destroy()
        self.current_frame = None

    # 主菜单
    def setup_main_menu(self):
        # 重设 self.current_frame
        self.clear_frame()
        self.current_frame = tk.Frame(self.root)
        self.current_frame.pack(fill='both', expand=True)

        # 加载背景图片
        bg_image = PhotoImage(file=os.path.join(os.path.dirname(__file__), "pictures/background.png"))
        bg_label = tk.Label(self.current_frame, image=bg_image)
        bg_label.image = bg_image  # 保持引用
        bg_label.place(x=0, y=0, relwidth=1, relheight=1)

        # 添加开始游戏按钮
        start_btn = tk.Button(self.current_frame, font=("宋体", 16), text="开始游戏", command=self.setup_match)
        start_btn.place(relx=0.5, rely=0.7, width=100, height=50, anchor='center')

    # 比赛轮次输入
    def setup_match(self):
        # 定义该环节父容器
        self.match_frame = tk.Frame(self.current_frame, bg="white", bd=5, relief="ridge")
        self.match_frame.place(relx=0.5, rely=0.5, relwidth=0.7, relheight=0.3, anchor='center')

        # 添加提示语和输入组件
        tip_label = tk.Label(self.match_frame, font=("宋体", 12), text="请输入比赛进行轮次")
        tip_label.place(relx=0.5, rely=0.3, relwidth=0.4, relheight=0.1, anchor='center')
        self.input = tk.Entry(self.match_frame, bd=3)
        # 控制键盘行为，仅允许输入数字
        self.input.bind("<Key>",lambda e: "break" if not e.char.isdigit() and e.keysym not in ("Left", "Right", "BackSpace", "Delete") else None)
        self.input.place(relx=0.5, rely=0.5, anchor='center')

        # 添加确认键（比赛开始）
        confirm = tk.Button(self.match_frame, font=("宋体", 12), text="确认", command=self.start_match)
        confirm.place(relx=0.3, rely=0.75, relwidth=0.2, relheight=0.2, anchor='center')

        # 添加取消键（回到主菜单）
        cancel = tk.Button(self.match_frame, font=("宋体", 12), text="取消", command=self.setup_main_menu)
        cancel.place(relx=0.7, rely=0.75, relwidth=0.2, relheight=0.2, anchor='center')

    # 比赛基本设置并准备开始
    def start_match(self):
        # 初始化玩家得分情况
        self.points = [{"id": i+1, "point": 0} for i in range(9)]
        # 获取输入的比赛总轮次，若输入为空，默认执行1轮
        self.matchs = self.input.get()
        if not self.matchs.strip():
            self.matchs = 1
        self.matchs = int(self.matchs)

        # 初始化当前游戏轮次并开始游戏
        self.match = 0
        self.start_game()

    # 开始游戏
    def start_game(self):
        # 初始化游戏状态
        self.match += 1
        self.game_over = False
        self.winner = None
        self.information = None
        self.day = 1
        self.players = []

        # 检测游戏日志是否存在，若存在则删除，防止上局游戏残留
        if hasattr(self, 'info_frame') and self.info_frame.winfo_exists():
            self.info_frame.destroy()
            self.info_frame = None

        # 创造玩家
        self.create_players()
        # 设置 UI
        self.setup_ui()

        # 定义线程之间通讯队列，第二线程运行游戏循环
        self.result_queue = Queue()
        self.root.after(1000, threading.Thread(target=self.game_loop, daemon=True).start())

        # 主线程实时更新维护 UI
        self.updating_ui()

    # 创造玩家
    def create_players(self):
        # 随机数抽取玩家身份
        self.roles = ["狼人", "狼人", "狼人", "平民", "平民", "平民", "预言家", "女巫", "猎人"]
        random.shuffle(self.roles)

        # 存储本局游戏特殊身份 ID
        self.wolf_ids = [i+1 for i, role in enumerate(self.roles) if role == "狼人"]
        for i, role in enumerate(self.roles):
            if role == "预言家":
                self.seer_id = i + 1
            elif role == "女巫":
                self.witch_id = i + 1
            elif role == "猎人":
                self.hunter_id = i + 1

        # 初始化大模型API和model设置（例子）
        exsample_Agents = []
        exsample_Agents.append({
            "API": "",
            "URL": "https://ark.cn-beijing.volces.com/api/v3",
            "model": "doubao-1-5-pro-32k-character-250228",
            "name": "豆包-1.5-pro"})
        exsample_Agents.append({
            "API": "",
            "URL": "https://openrouter.ai/api/v1",
            "model": "meta-llama/llama-4-maverick:free",
            "name": "llama-4-maverick"})
        exsample_Agents.append({
            "API": "",
            "URL": "https://generativelanguage.googleapis.com/v1beta/openai",
            "model": "gemini-2.0-flash",
            "name": "Gemini-2.0-flash"})
        exsample_Agents.append({
            "API": "",
            "URL": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "name": "DeepSeek-V3"})
        exsample_Agents.append({
            "API": "",
            "URL": "https://spark-api-open.xf-yun.com/v2",
            "model": "x1",
            "name": "讯飞星火-X1"})
        exsample_Agents.append({
            "API": "",
            "URL": "https://api.moonshot.cn/v1",
            "model": "kimi-latest",
            "name": "Kimi"})
        exsample_Agents.append({
            "API": "s",
            "URL": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": "qwen-max-latest",
            "name": "千问-max"})
        exsample_Agents.append({
            "API": "",
            "URL": "https://api.deepseek.com/v1",
            "model": "deepseek-reasoner",
            "name": "DeepSeek-R1"})
        exsample_Agents.append({
            "API": "",
            "URL": "https://free.v36.cm/v1",
            "model": "gpt-3.5-turbo-0125",
            "name": "GPT-3.5"})

        # 创建玩家，调用智能体类
        for i, role in enumerate(self.roles):
            # 基本规则阐述
            system_prompt = f"你是一名狼人杀玩家，正在参与一场一共由9名玩家组成的狼人杀游戏。请牢记在该局游戏中，一共有3名狼人，3名平民，1名预言家，1名女巫和1名猎人。本局游戏没有警长竞选环节，也没有警徽一说。白天发言顺序按夜晚死亡玩家的后置位开始依次发言。一旦所有村民死亡或者所有神职死亡，狼人将获得胜利。若狼人全部死亡则好人胜利。游戏结束时请所有人一起评选出本场发挥最好的玩家和发挥最差的玩家。预言家每晚可以查验一名玩家的身份，狼人彼此之间知晓自己的狼队友，且被允许可以自刀，女巫仅能使用一次解药和毒药，且在一个晚上不能同时使用解药和毒药，猎人只有被狼人杀死或被投票处决时可以开枪带走一位玩家，但被女巫毒杀时不能发动技能，存活状态不能开枪。"
            system_prompt += f"你在本局游戏中为{i+1}号玩家，身份为{role}，请牢记你的身份信息，请你保持冷静思考注重分析，尽全力帮助自己的阵营获得胜利，包括但不限于说谎搅混水穿别人身份等。"
            # 狼人额外告知其狼队友
            if role == "狼人":
                others = [id for id in self.wolf_ids if id != i+1]  # 排除自己
                system_prompt += f"本局游戏中，你的狼队友是：{', '.join(map(str, others))}号玩家，请你们互相配合，尽力取胜。玩狼人的状态，就是要会“装”，摆正心态，要把自己完全的代入好人角色，从好人视角去思考应该如何发言。如果不幸被预言家验到真实身份，千万不要慌，这时候可以伪装成其它神职身份，不仅可以最大限度保住自己，也可以尽快帮助队友，确认场上神职的位置。在于不要被别人发现你的视角，发言可以模棱两可一些，尽快找到神职，将其推出局。狼人互相之间可以知道队友，要完全配合队友"

            # 创建玩家，包含其大模型和各种状态
            self.players.append({
                "id": i + 1,
                "role": role,
                "alive": True,
                "Agent": Agents(exsample_Agents[i]["API"], exsample_Agents[i]["URL"], exsample_Agents[i]["model"], system_prompt),
                "name": exsample_Agents[i]["name"],
                # 如果是女巫，额外添加解药和毒药状态
                **({"antidote": True, "poison": True} if role == "女巫" else {})
            })

    # 设置 UI
    def setup_ui(self):
        # 更新前若有该局比赛日志信息则储存下来，防止伪更新 UI 将其删除
        if hasattr(self, 'event_log') and self.event_log.winfo_exists():
            self.information = self.event_log.get("1.0", "end").rstrip('\n')

        # 重设 self.current_frame
        self.clear_frame()
        self.current_frame = tk.Frame(self.root)
        self.current_frame.pack(fill='both', expand=True)

        # 背景设置
        UI_image = PhotoImage(file=os.path.join(os.path.dirname(__file__), "pictures/UI.png"))
        UI_label = tk.Label(self.current_frame, image=UI_image)
        UI_label.image = UI_image  # 保持引用
        UI_label.place(x=0, y=0, relwidth=1, relheight=1)
        # 游戏基本信息组件设置
        Title_label = tk.Label(self.current_frame, font=("楷体", 28), text="AI狼人杀锦标赛")
        Title_label.place(relx=0.5, rely=0.03, anchor='center')
        Match_label = tk.Label(self.current_frame, font=("楷体", 24), text=f"第 {self.match} / {self.matchs} 局")
        Match_label.place(relx=0.5, rely=0.1, anchor='center')
        Day = tk.Label(self.current_frame, font=("楷体", 20), text=f"第 {self.day} 天")
        Day.place(relx=0.5, rely=0.275, anchor='center')

        # 游戏信息面板
        self.info_frame = tk.Frame(self.current_frame, bg="white", bd=2, relief="ridge")
        self.info_frame.place(relx=0.5, rely=0.38, relwidth=0.9, relheight=0.15, anchor='center')
        self.event_log = tk.Text(self.info_frame, font=("宋体", 12), fg="black")
        self.event_log.pack()

        # 更新 UI 前保存下来的游戏日志信息重新添加回去
        if self.information:
            self.log_event(self.information)

        # 玩家相关信息和状态设置
        for i, player in enumerate(self.players):
            relx = 1/6 if i<5 else 5/6
            rely = (i+7)/12 if i<5 else (i+1)/10
            role_x = relx + (0.08 if i<5 else -0.08)
            role_image = PhotoImage(file=os.path.join(os.path.dirname(__file__), f"pictures/{player['role']}.png"))
            role_label = tk.Label(self.current_frame, image=role_image)
            role_label.image = role_image
            role_label.place(relx=role_x, rely=rely, anchor='center')
            # 女巫额外添加 解药和毒药 状态显示
            if player["role"] == "女巫":
                if player["antidote"]:
                    antidote_image = PhotoImage(file=os.path.join(os.path.dirname(__file__), "pictures/解药.png"))
                    antidote_label = tk.Label(self.current_frame, image=antidote_image)
                    antidote_label.image = antidote_image # 保持引用
                    antidote_label.place(relx=role_x + (0.05 if i<5 else -0.05), rely=rely+0.025, anchor='center')
                if player["poison"]:
                    poison_image = PhotoImage(file=os.path.join(os.path.dirname(__file__), "pictures/毒药.png"))
                    poison_label = tk.Label(self.current_frame, image=poison_image)
                    poison_label.image = poison_image # 保持引用
                    poison_label.place(relx=role_x + (0.05 if i<5 else -0.05), rely=rely-0.025, anchor='center')
            # 玩家存活状态显示
            if not player["alive"]:
                out_image = PhotoImage(file=os.path.join(os.path.dirname(__file__), "pictures/out.png"))
                out = tk.Label(self.current_frame, image=out_image)
                out.image = out_image  # 保持引用
                out.place(relx=relx, rely=rely, anchor='center')

        # 玩家积分设置
        self.points_frame = tk.Frame(self.current_frame, bg="white", bd=2, relief="ridge")
        self.points_frame.place(relx=0.5, rely=0.2, relwidth=0.9, relheight=0.1, anchor='center')

        # 配置 points_frame 的 grid 行列权重
        self.points_frame.grid_rowconfigure(0, weight=1)
        self.points_frame.grid_rowconfigure(1, weight=1)
        for col in range(len(self.players)):
            self.points_frame.grid_columnconfigure(col, weight=1)

        # 创建玩家名称标签（填满单元格）
        for col, player in enumerate(self.players):
            tk.Label(self.points_frame, text=f"玩家 {player['id']}", borderwidth=1, relief="solid").grid(row=0, column=col, sticky="nsew", padx=1, pady=1)

        # 创建玩家积分标签（填满单元格）
        for col, player in enumerate(self.players):
            tk.Label(self.points_frame, text=f"{self.points[col]['point']}", borderwidth=1, relief="solid").grid(row=1, column=col, sticky="nsew", padx=1, pady=1)

    # 游戏日志更新
    def log_event(self, message):
        self.event_log.insert(tk.END, message + "\n")
        self.event_log.see(tk.END)
        self.root.update()

    # 游戏逻辑循环
    def game_loop(self):
        # 夜晚阶段
        self.night_actions()
        # 白天阶段
        self.day_actions()

        # 游戏结束检测均在白天事件中，这里若游戏未结束延迟后游戏逻辑循环，若游戏结束准备本场游戏总结
        if not self.game_over:
            self.day += 1
            sleep(2)
            self.game_loop()
        else:
            sleep(2)
            # 本场游戏总结
            self.game_result()

    # 夜晚事件
    def night_actions(self):
        # 初始化夜晚死亡玩家的ID，self.will_death[0]为狼人杀死，self.will_death[1]为女巫毒死
        self.will_death = [0, 0]

        # 通过队列向主线程发送信息
        self.result_queue.put(("night",))
        # 告知各位玩家游戏进程
        for player in self.players:
            player["Agent"].tell(f"天黑请闭眼。（当前第{self.day}天夜晚）")

        # 预言家行动
        asyncio.run(self.voice.speak("天黑请闭眼，预言家请睁眼")) # 上帝语音播报
        if self.players[self.seer_id-1]["alive"]:
            answer = self.players[self.seer_id-1]["Agent"].chat("现在，你可以选择查验一位玩家的身份。你的回复应当是一个纯数字x，x为你要查验身份的玩家编号，不要过多阐述，直接给出x")
            answer = int(answer.strip()[0])
            role = self.players[answer-1]["role"]
            role = "好人" if role != "狼人" else "狼人"
            # 告知其查验目标身份
            self.players[self.seer_id-1]["Agent"].tell(f"{answer}号玩家的身份是{role}")
            # 通过队列向主线程发送预言家行动
            self.result_queue.put(("seer", answer, role))
        asyncio.run(self.voice.speak("你要验吗？你要验谁？")) # 上帝语音播报
        # 预言家行动结束，令主线程进行 UI 初始化
        self.result_queue.put(("set_up",))

        # 狼人行动
        self.wolf_words = []
        asyncio.run(self.voice.speak("预言家请闭眼，狼人请睁眼")) # 上帝语音播报
        # 狼人可先进行简单沟通，无序发言，盲发言，最后汇总告知
        for id in self.wolf_ids:
            if self.players[id-1]["alive"]:
                answer = self.players[id-1]["Agent"].chat("作为狼人，现在你可以与其他狼队友进行沟通，说出今晚想要杀死的玩家，并给出理由。你的回复应当尽量简短，200字即可。")
                answer = answer.strip() # 最大限度防止大模型错误输出
                self.wolf_words.append({
                    "id": id,
                    "words": answer
                })
                # 令主线程执行 UI 更新，同时进行狼人发言
                self.result_queue.put(("wolf_words", id, answer))
                asyncio.run(self.voice.speak(answer, id = id))
        # 狼人发言结束，令主线程执行 UI 初始化
        self.result_queue.put(("set_up",))

        # 传递狼人讨论结果
        for id in self.wolf_ids:
            if self.players[id-1]["alive"]:
                for other in self.wolf_words:
                    if other["id"] != id:
                        self.players[id-1]["Agent"].tell(f"{other['id']}号玩家认为" + f"{other['words']}")

        # 狼人投票
        wolf_votes = [{"id": i+1, "votes": 0} for i in range(9)]
        wolf_results = []
        for id in self.wolf_ids:
            if self.players[id-1]["alive"]:
                answer = self.players[id-1]["Agent"].chat("作为狼人，请根据所有信息投票给出今晚想要杀死的玩家。你的回复应当是一个纯数字x，x为你要投票杀死的玩家编号，不要过多阐述，直接给出x")
                answer = int(answer.strip()[0]) # 最大限度防止大模型错误输出
                wolf_votes[answer-1]["votes"] += 1
                wolf_results.append([id, answer])
        # 向主线程传递狼人投票结果
        self.result_queue.put(("wolf_votes", wolf_results))
        asyncio.run(self.voice.speak("你们要杀谁？")) # 上帝语音播报

        # 解析得票最多的玩家ID，若平票在其中随机选择
        max_votes = max(one["votes"] for one in wolf_votes)
        targets = [one["id"] for one in wolf_votes if one["votes"] == max_votes]
        self.will_death[0] = random.choice(targets) if len(targets) > 1 else targets[0]
        # 向主线程传递结果，进行游戏日志更新
        self.result_queue.put(("wolf_result", self.will_death[0]))
        # 向所有狼人同步信息
        for id in self.wolf_ids:
            if self.players[id-1]["alive"]:
                self.players[id-1]["Agent"].tell(f"你们准备杀死{self.will_death[0]}号玩家。")

        # 女巫行动
        asyncio.run(self.voice.speak("狼人请闭眼，女巫请睁眼。")) # 上帝语音播报
        if self.players[self.witch_id-1]["alive"]:
            if self.players[self.witch_id-1]["antidote"]:
                answer = self.players[self.witch_id-1]["Agent"].chat(f"{self.will_death[0]}号玩家将要死亡，你要对他使用解药救他吗？请直接回复救/不救，不要过多阐述")
                answer = answer.strip() # 最大限度防止大模型错误输出
                answer = re.sub(r'[^\w\s]', '', answer)
                # 向主线程传递结果
                self.result_queue.put(("witch_antidote", answer, self.will_death[0]))
                if answer == "救":
                    # 救下玩家更新状态
                    self.will_death[0] = 0
                    self.players[self.witch_id-1]["antidote"] = False

        asyncio.run(self.voice.speak("今晚要死的人是  ，你要救吗？")) # 上帝语音播报
        self.result_queue.put(("set_up",))

        # 若女巫未使用解药（同一晚不能同时使用解药和毒药）
        if self.players[self.witch_id-1]["alive"] and self.will_death[0] != 0:
            if self.players[self.witch_id-1]["poison"]:
                answer = self.players[self.witch_id-1]["Agent"].chat(f"你要使用毒药吗？如果用，你的回复应当是一个纯数字x，x为你要用毒药杀死的玩家编号，直接给出x，不要过多阐述，；如果不用，请直接回复不用，不要过多阐述。")
                answer = answer.strip() # 最大限度防止大模型错误输出
                answer = re.sub(r'[^\w\s]', '', answer)
                # 向主线程传递结果
                self.result_queue.put(("witch_poison", answer))
                if answer != "不用":
                    # 毒杀玩家更新状态
                    self.will_death[1] = int(answer[0])
                    self.players[self.witch_id-1]["poison"] = False

        asyncio.run(self.voice.speak("你要使用毒药吗？你要毒谁？")) # 上帝语音播报
        self.result_queue.put(("set_up",))

    # 白天事件
    def day_actions(self):
        self.result_queue.put(("day",))

        # 处理夜晚死亡，向各位玩家同步
        if self.will_death[0] == 0 and self.will_death[1] == 0:
            for player in self.players:
                player["Agent"].tell(f"天亮了，昨天是平安夜。（当前第{self.day}天白天）")
            asyncio.run(self.voice.speak("天亮了，昨天是平安夜。"))
        elif self.will_death[0] != 0 and (self.will_death[1] == 0 or self.will_death[0] == self.will_death[1]):
            for player in self.players:
                player["Agent"].tell(f"天亮了，昨天{self.will_death[0]}号玩家死亡。（当前第{self.day}天白天）")
            asyncio.run(self.voice.speak(f"天亮了，昨天{self.will_death[0]}号玩家死亡。"))
            self.players[self.will_death[0]-1]["alive"] = False
        elif self.will_death[0] != 0 and self.will_death[1] != 0:
            for player in self.players:
                player["Agent"].tell(f"天亮了，昨天{self.will_death[0]}号玩家和{self.will_death[1]}号玩家死亡。（当前第{self.day}天白天）")
            asyncio.run(self.voice.speak(f"天亮了，昨天{self.will_death[0]}号玩家和{self.will_death[1]}号玩家死亡。"))
            self.players[self.will_death[0]-1]["alive"] = False
            self.players[self.will_death[1]-1]["alive"] = False
        self.result_queue.put(("set_up",))
        # 夜晚死亡处理完成，检测游戏是否结束
        self.check_game_over()
        if self.game_over:
            return

        # 若猎人夜晚仅被狼人所杀（女巫毒杀不能释放技能）
        if self.will_death[0] != 0 and self.will_death[0] != self.will_death[1] and self.players[self.will_death[0]-1]["role"] == "猎人":
            answer = self.players[self.will_death[0]-1]["Agent"].chat("你作为猎人已经死亡，现在你可以选择一名玩家开枪将其带走。你的回复应当是一个纯数字x，x为你要开枪杀死的玩家编号，不要过多阐述，直接给出x")
            answer = int(answer.strip()[0])
            self.result_queue.put(("hunter", answer))
            # 告知各位玩家结果并向主线程同步
            for player in self.players:
                player["Agent"].tell(f"{self.will_death[0]}号玩家身份为猎人，他选择开枪带走{answer}号玩家。")
            asyncio.run(self.voice.speak(f"{self.will_death[0]}号玩家身份为猎人，他选择开枪带走{answer}号玩家。"))
            self.players[answer-1]["alive"] = False
            self.result_queue.put(("set_up",))

            # 猎人带走玩家，检测游戏是否结束
            self.check_game_over()
            if self.game_over:
                return
            self.will_death.append(answer)

        # 游戏未结束，若为第一晚可发表遗言
        if self.day == 1:
            for id in self.will_death:
                if id != 0:
                    self.out_words(id)

        # 游戏未结束，按一定顺序发言
        for player in self.players:
                player["Agent"].tell(f"现在将按顺序进行发言。")
        asyncio.run(self.voice.speak("现在将按顺序进行发言。"))
        for i in range(9):
            id = i + self.will_death[0] + 1
            if id > 9:
                id -= 9
            # 每位存活玩家发言并向其他玩家和主线程同步
            if self.players[id-1]["alive"]:
                answer = self.players[id-1]["Agent"].chat("现在该你发言。你的所有输出都将同步给其他所有玩家，绝对不要出现内心活动和想法，不要在括号里表明自己的目的和行为。你的发言应当有利于自己的阵营走向胜利。你的回复应当尽量简短，200字即可。")
                answer = answer.strip()
                answer = re.sub(r'\([^)]*\)', '', answer) # 删除()内容，有时AI会有内心戏
                for player in self.players:
                    player["Agent"].tell(f"{id}号玩家发言如下：" + answer)
                # 玩家发言并发送给主线程
                self.result_queue.put(("all_words", id, answer))
                asyncio.run(self.voice.speak(answer, id = id))
        self.result_queue.put(("set_up",))

        # 玩家投票
        all_votes = [{"id": i+1, "votes": 0} for i in range(9)]
        all_results = []
        give_up = 0
        for player in self.players:
            if player["alive"]:
                answer = player["Agent"].chat("现在，你必须给出今天想要投票的玩家。你的回复应当是一个纯数字x，x为你要投票出局的玩家编号，不要过度思考或过多阐述，直接给出一个纯数字x。如果弃票，请直接回复弃票，不要过多阐述。")
                answer = answer.strip()  # 最大限度防止大模型不符合格式输出
                answer = re.sub(r'[^\w\s]', '', answer)
                if answer == "弃票":
                    give_up += 1
                    all_results.append([player["id"], answer])
                else:
                    answer = int(answer[0])
                    all_votes[answer-1]["votes"] += 1
                    all_results.append([player["id"], answer])
        # 向主线程发送投票结果，同时上帝进行播报
        self.result_queue.put(("all_votes", all_results))
        asyncio.run(self.voice.speak("发言结束，现在开始投票。"))
        # 同步投票信息
        votes_info = ""
        for one in all_results:
            if one[1] == "弃票":
                votes_info += f"{one[0]}号玩家弃票"
            else:
                votes_info += f"{one[0]}号玩家投票给{one[1]}号玩家"
        for player in self.players:
            player["Agent"].tell("投票信息如下：" + votes_info)

        # 解析得票最多的玩家ID，若平票或弃票过半作废
        max_votes = max(one["votes"] for one in all_votes)
        targets = [one["id"] for one in all_votes if one["votes"] == max_votes]
        the_death = 0 if len(targets) > 1 else targets[0]
        if give_up >= max_votes:
            the_death = 0

        # 向主线程发送结果并向所有玩家同步
        self.result_queue.put(("all_result", the_death))
        day_result = f"{the_death}号玩家被投票处决。" if the_death != 0 else "平票或弃票过半，今天没有人被处决。"
        for player in self.players:
            player["Agent"].tell(day_result)
        asyncio.run(self.voice.speak(day_result))
        if the_death != 0:
            self.players[the_death-1]["alive"] = False
        self.result_queue.put(("set_up",))

        # 玩家被投票处决检测游戏是否结束
        self.check_game_over()
        if self.game_over:
            return

        # 若猎人被处决
        if the_death != 0 and self.players[the_death-1]["role"] == "猎人":
            answer = self.players[the_death-1]["Agent"].chat("你作为猎人已经死亡，现在你可以选择一名玩家开枪将其带走。你的回复应当是一个纯数字x，x为你要开枪杀死的玩家编号，不要过多阐述，直接给出x")
            answer = int(answer.strip()[0])
            # 告知各位玩家结果并向主线程同步
            self.result_queue.put(("hunter", answer))
            for player in self.players:
                player["Agent"].tell(f"{the_death}号玩家身份为猎人，他选择开枪带走{answer}号玩家。")
            asyncio.run(self.voice.speak(f"{the_death}号玩家身份为猎人，他选择开枪带走{answer}号玩家。"))
            self.players[answer-1]["alive"] = False
            self.result_queue.put(("set_up",))
            # 猎人带走玩家，检测游戏是否结束
            self.check_game_over()
            if self.game_over:
                return
            # 若未结束，发表遗言
            self.out_words(the_death)
            self.out_words(answer)
            return
        # 非猎人被处决，直接发表遗言
        self.out_words(the_death)

    # 发表遗言
    def out_words(self, id):
        answer = self.players[id-1]["Agent"].chat("你已死亡，现在可以发表遗言。你的发言将会同步给在场所有玩家，不要出现内心潜台词和内心想法，你的遗言应当是有利于自己阵营的发言。")
        answer = answer.strip()
        answer = re.sub(r'\([^)]*\)', '', answer) # 删除()内容，有时AI会有内心戏
        # 玩家遗言同步给所有玩家并发送到主线程
        for player in self.players:
            player["Agent"].tell(f"{id}号玩家遗言如下：" + answer)
        asyncio.run(self.voice.speak(f"请{id}号玩家发表遗言"))
        self.result_queue.put(("all_words", id, answer))
        asyncio.run(self.voice.speak(answer, id = id))
        # 更新UI
        self.result_queue.put(("set_up",))

    # 游戏运行过程中，主线程实时更新 UI
    def updating_ui(self):
        # 读取队列信息
        while not self.result_queue.empty():
            result = self.result_queue.get_nowait()
            event_type = result[0]

            # 根据事件类型，分类进行不同处理
            if event_type == "set_up":
                self.setup_ui()
            elif event_type == "night":
                self.log_event(f"================================== 第 {self.day} 天夜晚 =================================")
            elif event_type == "day":
                self.log_event(f"================================== 第 {self.day} 天白天 =================================")

            # 预言家行动信息
            elif event_type == "seer":
                _, answer, role = result
                self.setup_ui()
                seer_label = tk.Label(self.current_frame, font=("宋体", 20), text=f"查验{answer}号")
                i = self.seer_id-1
                relx = 1/6 if i<5 else 5/6
                relx = relx + (0.2 if i<5 else -0.2)
                rely = (i+7)/12 if i<5 else (i+1)/10
                seer_label.place(relx=relx, rely=rely, anchor='center')
                self.log_event(f"{self.seer_id}号玩家(预言家)查验{answer}号玩家({self.players[answer-1]['role']})身份为{role}")

            # 狼人发言信息
            elif event_type == "wolf_words":
                _, id, answer = result
                self.setup_ui()
                i = id-1
                relx = 1/6 if i<5 else 5/6
                rely = (i+7)/12 if i<5 else (i+1)/10
                # 发言状态显示
                speak_image = PhotoImage(file=os.path.join(os.path.dirname(__file__), "pictures/speak.png"))
                speak_label = tk.Label(self.current_frame, image=speak_image)
                speak_label.image = speak_image  # 保持引用
                speak_label.place(relx=relx, rely=rely, anchor='center')
                # 发言内容显示
                self.speak_frame = tk.Frame(self.current_frame, bg="white", bd=2, relief="ridge")
                self.speak_frame.place(relx=0.5, rely=0.75, relwidth=0.33, relheight=0.3, anchor='center')
                temp_Text = tk.Text(self.speak_frame, font=("宋体", 12), fg="black")
                temp_Text.pack(expand=True, fill='both')
                temp_Text.insert(tk.END, answer)
                temp_Text.see(tk.END)
                self.root.update()

            # 狼人投票信息
            elif event_type == "wolf_votes":
                _, wolf_results = result
                self.setup_ui()
                for one in wolf_results:
                    vote_label = tk.Label(self.current_frame, font=("宋体", 20), text=f"{one[1]}号")
                    i = one[0]-1
                    relx = 1/6 if i<5 else 5/6
                    relx = relx + (0.15 if i<5 else -0.15)
                    rely = (i+7)/12 if i<5 else (i+1)/10
                    vote_label.place(relx=relx, rely=rely, anchor='center')

            # 狼人行动结果
            elif event_type == "wolf_result":
                _, result = result
                self.setup_ui()
                # 女巫无解药，直接杀死更新日志
                if not self.players[self.witch_id-1]["antidote"]:
                    self.log_event(f"狼人杀死了{result}号玩家({self.players[result-1]['role']})")

            # 女巫解药信息
            elif event_type == "witch_antidote":
                _, answer, the_death = result
                self.setup_ui()
                antidote_label = tk.Label(self.current_frame, font=("宋体", 20), text=answer)
                i = self.witch_id-1
                relx = 1/6 if i<5 else 5/6
                relx = relx +  (0.18 if i<5 else -0.18)
                rely = (i+7)/12 if i<5 else (i+1)/10
                antidote_label.place(relx=relx, rely=rely, anchor='center')
                # 根据实际行动结果更新日志
                if answer == "救":
                    self.log_event(f"{self.witch_id}号玩家(女巫)使用解药救下{the_death}号玩家({self.players[the_death-1]['role']})")
                else:
                    self.log_event(f"狼人杀死了{the_death}号玩家({self.players[the_death-1]['role']})")

            # 女巫毒药信息
            elif event_type == "witch_poison":
                _, answer = result
                self.setup_ui()
                if answer != "不用":
                    answer = int(answer.strip()[0])
                    poison_label = tk.Label(self.current_frame, font=("宋体", 20), text=f"毒杀{answer}号")
                else:
                    poison_label = tk.Label(self.current_frame, font=("宋体", 20), text=answer)
                i = self.witch_id-1
                relx = 1/6 if i<5 else 5/6
                relx = relx + (0.2 if i<5 else -0.2)
                rely = (i+7)/12 if i<5 else (i+1)/10
                poison_label.place(relx=relx, rely=rely, anchor='center')
                # 根据实际行动结果更新日志
                if answer != "不用":
                    self.log_event(f"{self.witch_id}号玩家(女巫)毒杀{answer}号玩家({self.players[answer-1]['role']})")

            # 全体发言信息
            elif event_type == "all_words":
                _, id, answer = result
                self.setup_ui()
                i = id-1
                relx = 1/6 if i<5 else 5/6
                rely = (i+7)/12 if i<5 else (i+1)/10
                # 发言状态显示
                speak_image = PhotoImage(file=os.path.join(os.path.dirname(__file__), "pictures/speak.png"))
                speak_label = tk.Label(self.current_frame, image=speak_image)
                speak_label.image = speak_image  # 保持引用
                speak_label.place(relx=relx, rely=rely, anchor='center')
                # 发言内容显示
                self.speak_frame = tk.Frame(self.current_frame, bg="white", bd=2, relief="ridge")
                self.speak_frame.place(relx=0.5, rely=0.75, relwidth=0.33, relheight=0.3, anchor='center')
                temp_Text = tk.Text(self.speak_frame, font=("宋体", 12), fg="black")
                temp_Text.pack(expand=True, fill='both')
                temp_Text.insert(tk.END, answer)
                temp_Text.see(tk.END)
                self.root.update()

            # 全体投票信息
            elif event_type == "all_votes":
                _, all_results = result
                self.setup_ui()
                for one in all_results:
                    text = "弃票" if one[1] == "弃票" else f"{one[1]}号"
                    vote_label = tk.Label(self.current_frame, font=("宋体", 20), text=text)
                    i = one[0]-1
                    relx = 1/6 if i<5 else 5/6
                    relx = relx + (0.15 if i<5 else -0.15)
                    rely = (i+7)/12 if i<5 else (i+1)/10
                    vote_label.place(relx=relx, rely=rely, anchor='center')

            # 全体投票结果
            elif event_type == "all_result":
                _, result = result
                self.setup_ui()
                if result != 0:
                    self.log_event(f"{result}号玩家({self.players[result-1]['role']})被投票处决")
                else:
                    self.log_event(f"平票或弃票过半，今天没有人被投票处决")

            # 猎人行动信息
            elif event_type == "hunter":
                _, answer = result
                self.setup_ui()
                hunter_label = tk.Label(self.current_frame, font=("宋体", 20), text=f"带走{answer}号")
                i = self.hunter_id-1
                relx = 1/6 if i<5 else 5/6
                relx = relx + (0.2 if i<5 else -0.2)
                rely = (i+7)/12 if i<5 else (i+1)/10
                hunter_label.place(relx=relx, rely=rely, anchor='center')
                self.log_event(f"{self.hunter_id}号玩家(猎人)开枪带走{answer}号玩家({self.players[answer-1]['role']})")

            # 游戏结束信息
            elif event_type == "game_over":
                self.setup_ui()
                self.log_event(f"游戏结束!\n{self.winner}阵营获胜！")
                result_frame = tk.Frame(self.current_frame, bg="black", bd=5, relief="ridge")
                result_frame.place(relx=0.5, rely=0.5, relwidth=0.7, relheight=0.3, anchor='center')
                game_result = tk.Label(result_frame, text=f"游戏结束!\n\n{self.winner}阵营获胜！", font=("楷体", 30), fg="gold", bg="black")
                game_result.place(relx=0.5, rely=0.5, anchor='center')

            # MVP和战犯投票信息
            elif event_type == "game_votes":
                _, game_results = result
                self.setup_ui()
                for one in game_results:
                    vote_label = tk.Label(self.current_frame, font=("宋体", 20), text=f"MVP:{one[1]}号\n战犯:{one[2]}号")
                    i = one[0]-1
                    relx = 1/6 if i<5 else 5/6
                    relx = relx + (0.14 if i<5 else -0.14)
                    rely = (i+7)/12 if i<5 else (i+1)/10
                    vote_label.place(relx=relx, rely=rely, anchor='center')

            # MVP和战犯结果
            elif event_type == "game_result":
                _, mvp, lvp = result
                self.setup_ui()
                # 设置本环节父容器
                result_frame = tk.Frame(self.current_frame, bg="white", bd=5, relief="ridge")
                result_frame.place(relx=0.5, rely=0.5, relwidth=0.8, relheight=0.4, anchor='center')
                # 文字显示
                mvp_label = tk.Label(result_frame, font=("楷体", 20), text=f"MVP :      {self.players[mvp-1]['name']}")
                mvp_label.place(relx=0.3, rely=0.3, anchor='w')
                lvp_label = tk.Label(result_frame, font=("楷体", 20), text=f"战犯:      {self.players[lvp-1]['name']}")
                lvp_label.place(relx=0.3, rely=0.7, anchor='w')
                # 头像显示
                mvp_image = PhotoImage(file=os.path.join(os.path.dirname(__file__), f"pictures/players/{self.players[mvp-1]['name']}.png"))
                MVP_label = tk.Label(result_frame, image=mvp_image)
                MVP_label.image = mvp_image  # 保持引用
                MVP_label.place(relx=0.5, rely=0.3, anchor='center')
                lvp_image = PhotoImage(file=os.path.join(os.path.dirname(__file__), f"pictures/players/{self.players[lvp-1]['name']}.png"))
                LVP_label = tk.Label(result_frame, image=lvp_image)
                LVP_label.image = lvp_image  # 保持引用
                LVP_label.place(relx=0.5, rely=0.7, anchor='center')
                # 检测比赛是否结束
                if self.match == self.matchs:
                    self.root.after(4000, self.setup_end)
                else:
                    self.root.after(4000, self.start_game)
                # 本局游戏结束，跳出循环
                return

        # 每隔100ms检查一次队列
        self.root.after(100, self.updating_ui)

    # 检查游戏是否结束
    def check_game_over(self):
        wolves = [p for p in self.players if p["role"] == "狼人" and p["alive"]]
        villagers = [p for p in self.players if p["role"] == "平民" and p["alive"]]
        gods = [p for p in self.players if p["role"] != "狼人" and p["role"] != "平民" and p["alive"]]
        # 神职全死，狼人胜利
        if not gods:
            self.game_over = True
            self.winner = "狼人"
        # 平民全死，狼人胜利
        elif not villagers:
            self.game_over = True
            self.winner = "狼人"
        # 狼人全死，有神职和平民存活，好人胜利
        elif not wolves:
            self.game_over = True
            self.winner = "好人"

    # 游戏结束，表现评分
    def game_result(self):
        # 游戏结束播报
        self.result_queue.put(("game_over",))
        asyncio.run(self.voice.speak(f"游戏结束！{self.winner}获胜！"))
        # 本局身份信息公开
        role_info = ""
        for i, role in enumerate(self.roles):
            role_info += f"{i+1}号玩家 : {role}\n"
        # 本局游戏日志公开
        self.game_log = self.event_log.get("1.0", "end-1c")
        # 初始化投票
        mvp_votes = [{"id": i+1, "votes": 0} for i in range(9)]
        lvp_votes = [{"id": i+1, "votes": 0} for i in range(9)]
        game_results = []

        # 玩家依次投票
        for i, player in enumerate(self.players):
            player["alive"] = True
            player["Agent"].tell(f"游戏结束，{self.winner}获胜！本局游戏所有玩家身份信息如下：{role_info}。整场游戏日志如下：{self.game_log}")
            if player["role"] == "女巫":
                player["antidote"] = False
                player["poison"] = False
            if self.winner == "狼人" and player["role"] == "狼人":
                self.points[i]["point"] += 10
            elif self.winner == "好人" and player["role"] != "狼人":
                self.points[i]["point"] += 10
            answer = player["Agent"].chat("现在请你根据本场游戏的所有信息，投票选出本场游戏发挥最佳的玩家和发挥最差的玩家。你的输出应当严格遵照'x-y'的格式，其中x为你认为本场发挥最佳的玩家编号，y为你认为本场发挥最差的玩家编号。不要过多阐述，直接给出'x-y'，严格遵守'x-y'格式")
            try:
                mvp, lvp = map(lambda x: int(x.strip()[0]), answer.split("-"))  # 用 split 分割并转为整数
            except AttributeError:
                integers = re.findall(r"\d+", answer)
                mvp, lvp = int(integers[0]), int(integers[1])
            mvp_votes[mvp-1]["votes"] += 1
            lvp_votes[lvp-1]["votes"] += 1
            game_results.append([i+1, mvp, lvp])
        # 将结果发送给主线程并播报
        self.result_queue.put(("game_votes", game_results))
        asyncio.run(self.voice.speak("请投票选出本场游戏的MVP和战犯。"))
        sleep(2)

        # 得出本局 mvp 和 lvp
        max_mvp_votes = max(one["votes"] for one in mvp_votes)
        max_lvp_votes = max(one["votes"] for one in lvp_votes)
        targets = [one["id"] for one in mvp_votes if one["votes"] == max_mvp_votes]
        mvp = random.choice(targets) if len(targets) > 1 else targets[0]
        targets = [one["id"] for one in lvp_votes if one["votes"] == max_lvp_votes]
        lvp = random.choice(targets) if len(targets) > 1 else targets[0]
        self.points[mvp-1]["point"] += 5
        self.points[lvp-1]["point"] -= 5
        self.result_queue.put(("game_result", mvp, lvp))

    # 比赛结束进行结算
    def setup_end(self):
        self.clear_frame()
        self.current_frame = tk.Frame(self.root)
        self.current_frame.pack(fill='both', expand=True)
        # 加载背景图片
        bg_image = PhotoImage(file=os.path.join(os.path.dirname(__file__), "pictures/background.png"))
        bg_label = tk.Label(self.current_frame, image=bg_image)
        bg_label.image = bg_image  # 保持引用
        bg_label.place(x=0, y=0, relwidth=1, relheight=1)

        # 全场最佳
        self.points.sort(key=lambda x: x["point"], reverse=True)
        fmvp_id = self.points[0]["id"]
        fmvp_label = tk.Label(self.current_frame, font=("楷体", 28), text=f"全场最佳:     {self.players[fmvp_id-1]['name']}")
        fmvp_label.place(relx=0.2, rely=0.1, anchor='w')

        fmvp_image = PhotoImage(file=os.path.join(os.path.dirname(__file__), f"pictures/players/{self.players[fmvp_id-1]['name']}.png"))
        FMVP_label = tk.Label(self.current_frame, image=fmvp_image)
        FMVP_label.image = fmvp_image  # 保持引用
        FMVP_label.place(relx=0.5, rely=0.1, anchor='center')
        fmvp_image = PhotoImage(file=os.path.join(os.path.dirname(__file__), f"pictures/players/fmvp.png"))
        FMVP_label = tk.Label(self.current_frame, image=fmvp_image)
        FMVP_label.image = fmvp_image  # 保持引用
        FMVP_label.place(relx=0.5, rely=0.05, anchor='center')

        # 积分一览
        for i, one in enumerate(self.points):
            image = PhotoImage(file=os.path.join(os.path.dirname(__file__), f"pictures/players/{self.players[one['id']-1]['name']}.png"))
            image_label = tk.Label(self.current_frame, image=image)
            image_label.image = image
            image_label.place(relx=0.3, rely=0.18+i*0.08, anchor='center')
            text_label = tk.Label(self.current_frame, font=("楷体", 20), text=f" {self.players[one['id']-1]['name']} : {one['point']}")
            text_label.place(relx=0.38, rely=0.18+i*0.08, anchor='w')

        # 添加返回菜单按钮
        return_btn = tk.Button(self.current_frame, font=("宋体", 16), text="返回主菜单", command=self.setup_main_menu)
        return_btn.place(relx=0.5, rely=0.9, width=150, height=50, anchor='center')

# 主程序入口
if __name__ == "__main__":
    # 初始化语音库
    pygame.mixer.init()
    # 运行游戏
    game = WerewolfGame()
    game.root.mainloop()