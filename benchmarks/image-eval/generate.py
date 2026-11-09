"""Create the public synthetic image evaluation set in a new directory.

Requires Pillow and a font containing Korean glyphs. No external calls are made.
"""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True, help='New output directory')
    parser.add_argument('--font', type=Path, required=True, help='Font supporting Korean text')
    args = parser.parse_args()
    large = ImageFont.truetype(str(args.font), 36)
    small = ImageFont.truetype(str(args.font), 27)
    args.output.mkdir(parents=True, exist_ok=False)

    image = Image.new('RGB', (900, 500), 'white')
    draw = ImageDraw.Draw(image)
    draw.text((50, 45), '환불 안내', font=large, fill='black')
    draw.text((50, 125), '배송 후 7일 이내 신청', font=large, fill='black')
    draw.text((50, 210), '예외: 주문 제작 상품은 제외', font=large, fill='black')
    draw.text((50, 300), '결제 금액: 12,500원', font=large, fill='black')
    image.save(args.output/'text.png')

    image = Image.new('RGB', (900, 500), '#b9dcf1')
    draw = ImageDraw.Draw(image)
    draw.ellipse((685, 50, 795, 160), fill='#f6c645')
    draw.polygon([(0, 390), (255, 130), (470, 390)], fill='#61866a')
    draw.polygon([(270, 390), (560, 95), (850, 390)], fill='#7fa184')
    draw.rectangle((0, 390, 899, 499), fill='#679bc0')
    image.save(args.output/'no-text.png')

    image = Image.new('RGB', (900, 500), 'white')
    draw = ImageDraw.Draw(image)
    draw.text((250, 20), '월별 주문 수', font=large, fill='black')
    draw.line([(120, 90), (120, 400), (800, 400)], fill='black', width=4)
    for x, label, height, value in [(220, '1월', 100, '10'), (390, '2월', 200, '20'), (560, '3월', 150, '15')]:
        draw.rectangle((x, 400-height, x+90, 399), fill='#4784b8')
        draw.text((x+22, 405), label, font=small, fill='black')
        draw.text((x+26, 365-height), value, font=small, fill='black')
    image.save(args.output/'chart.png')

    image = Image.new('RGB', (900, 500), 'white')
    draw = ImageDraw.Draw(image)
    for x, title in [(30, '신청'), (340, '검토'), (650, '완료')]:
        draw.rounded_rectangle((x, 170, x+210, 260), radius=12, outline='black', width=4)
        draw.text((x+65, 192), title, font=large, fill='black')
    for x in (240, 550):
        draw.line((x, 215, x+85, 215), fill='black', width=5)
        draw.polygon([(x+85, 215), (x+67, 205), (x+67, 225)], fill='black')
    image.save(args.output/'flow.png')

    image = Image.new('RGB', (900, 500), 'white')
    draw = ImageDraw.Draw(image)
    draw.text((50, 65), '주문번호:', font=large, fill='black')
    draw.rectangle((260, 60, 570, 115), fill='black')
    draw.text((50, 170), '상태: 확인 필요', font=large, fill='black')
    image.save(args.output/'occluded.png')
    print('Created five synthetic PNG fixtures in', args.output)


if __name__ == '__main__':
    main()
