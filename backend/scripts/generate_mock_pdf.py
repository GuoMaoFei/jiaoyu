import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import unicodedata

def create_mock_textbook():
    pdf_path = "mock_textbook_math_grade1.pdf"
    c = canvas.Canvas(pdf_path, pagesize=A4)
    width, height = A4

    # Use a system font that supports Chinese (Microsoft YaHei on Windows)
    try:
        pdfmetrics.registerFont(TTFont('msyh', 'msyh.ttc'))
        font_name = 'msyh'
    except:
        font_name = 'Helvetica' # Fallback, Chinese might not render well but it won't crash

    def draw_text(text, x, y, size=12):
        c.setFont(font_name, size)
        c.drawString(x, y, text)

    # Title Page
    draw_text("小学数学 一年级上册 (测试教材)", width/2 - 120, height/2 + 50, size=24)
    draw_text("AI 智能教育辅助平台 内部测试版", width/2 - 100, height/2, size=16)
    c.showPage()
    
    # Table of Contents
    draw_text("目录", width/2 - 30, height - 80, size=20)
    draw_text("第一单元 准备课 .......................... 1", 100, height - 150, size=14)
    draw_text("第二单元 位置 ............................ 2", 100, height - 180, size=14)
    draw_text("第三单元 1~5的认识和加减法 ............... 3", 100, height - 210, size=14)
    draw_text("第四单元 认识图形 ........................ 4", 100, height - 240, size=14)
    c.showPage()

    # Chapter 1
    draw_text("第一单元：准备课", width/2 - 80, height - 80, size=20)
    draw_text("1. 数一数", 100, height - 140, size=16)
    text_lines = [
        "数数是数学的基础。在大自然中，我们可以多数一数。",
        "举例：天上有1个太阳，草地上有2只小兔，3只蝴蝶。",
        "学习目标：能准确指出物体的数量，并掌握0的概念。",
        "在实际生活中，遇到多个物品，可以用手指逐个数出。"
    ]
    y = height - 180
    for line in text_lines:
        draw_text(line, 100, y, size=12)
        y -= 25
    c.showPage()

    # Chapter 2
    draw_text("第二单元：位置", width/2 - 70, height - 80, size=20)
    draw_text("2. 上下、前后、左右", 100, height - 140, size=16)
    text_lines2 = [
        "认识空间位置是立体思维的开端。",
        "“上”指高处，“下”指低处。例如树在土上，根在土下。",
        "“前”指面对的方向，“后”指背对的方向。",
        "“左”和“右”与双手有关，拿筷子的一般是右手。",
        "考点：给出图片，能说出小明在小红的哪一边。"
    ]
    y = height - 180
    for line in text_lines2:
        draw_text(line, 100, y, size=12)
        y -= 25
    c.showPage()

    # Chapter 3
    draw_text("第三单元：1~5的认识和加减法", width/2 - 110, height - 80, size=20)
    draw_text("3. 加法和减法", 100, height - 140, size=16)
    text_lines3 = [
        "加法就是将两个数字合并成一个更大的数字，用“+”表示。",
        "举例：1只鸟飞来，又飞来2只鸟，一共是 1+2=3 只鸟。",
        "减法就是从一个总数里拿走一部分，用“-”表示。",
        "举例：盘里有4个苹果，吃掉了1个，还剩 4-1=3 个。",
        "基础口诀：1加1等于2，2加2等于4。做错会扣健康分数哦。"
    ]
    y = height - 180
    for line in text_lines3:
        draw_text(line, 100, y, size=12)
        y -= 25
    c.showPage()

    c.save()
    print("PDF generated at:", os.path.abspath(pdf_path))

if __name__ == "__main__":
    create_mock_textbook()
