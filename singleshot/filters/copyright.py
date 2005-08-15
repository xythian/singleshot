import os
import ImageFont
import ImageDraw
import ImageEnhance

def pil_filter(size, input):
    font = ImageFont.load_default()
    draw = ImageDraw.Draw(input)
    draw.rectangle(( (0,0), (size, 20)), fill=(0,0,0))
    draw.text((20,0), 'Copyright 2005', font=font, fill=(255,255,255))
    del draw

