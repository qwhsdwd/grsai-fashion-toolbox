FRAMING = '''完整构图优先：完整头部和五官、整个上衣、腰带、整个裙子或裤子及其下摆同时入镜。
拍摄范围从头顶至膝盖或更远，头顶留出约10%的背景，下摆下方有腿部空间，人物居中，双手有活动余量。
不裁切发顶、额头、眼睛或衣服下摆，手和物体不遮脸，保持真实自然的身体比例。'''


def text_prompt(text, full_outfit):
    return text.strip() + ('\n\n' + FRAMING if full_outfit else '')


def outfit_prompt(instructions, full_outfit, has_bottom, has_pose):
    lines = [
        '生成一张自然真实的人物换装照片。图1是唯一的人物身份来源，图2只提供目标服装。',
        '保留图1人物的脸、发型、肤色、年龄特征与体型，背景和光线尽量保持一致。',
        '图2可以是平铺服装、挂拍服装，或另一个人穿着的服装；只提取衣服的版型、材质、配色、图案、领口、袖口、纽扣和装饰。',
        '不要复制图2穿衣者的脸、头发、体型或背景。让图2衣服自然穿在图1人物身上，贴合体型，有真实褶皱和遮挡关系；移除被替换的原衣服，保留未指定替换的其他服饰。',
    ]
    if has_bottom:
        lines += ['图3另行提供下装；图2用于上衣，图3用于裙子或裤子，同时穿到图1人物身上。图3只提取服装，不复制其人物身份或背景。']
    if has_pose:
        index = 4 if has_bottom else 3
        lines += [f'图{index}只提供姿势和构图。尽量模仿其肢体姿态、站姿、手臂和腿的位置，保持解剖自然；不复制其脸、衣服或背景，人物身份仍由图1决定。']
    else:
        lines += ['保持图1人物原本的姿势和身体比例。']
    if full_outfit:
        lines += [FRAMING]
    if instructions.strip():
        lines += ['补充要求：' + instructions.strip()]
    lines += ['只输出一张成品照片，无拼图、对比排版、衣架、额外人物、额外肢体、文字、水印或Logo。']
    return '\n\n'.join(lines)


def video_prompt(keywords, duration, full_outfit, has_pose):
    lines = [f'{duration}秒，写实服装模特展示短视频，一镜到底。图1决定唯一人物的脸、发型、衣服、场景和光线，整段保持一致。']
    if full_outfit:
        lines += [FRAMING, '全程同时保持完整露脸和整套衣服入镜，镜头固定，不推近、不变焦，人物不向镜头走近；所有动作服从完整构图。']
    if has_pose:
        lines += ['图2只提供造型和姿势参考。模特在视频中自然过渡到图2的肢体姿态并短暂停留，尽量模仿其站姿、手和腿的位置，不复制其脸、衣服或背景。']
    if keywords.strip():
        lines += ['动作与展示要求：' + keywords.strip()]
    else:
        lines += ['自然微笑看向镜头，正面站姿、轻侧身、轻扶胯、轻展裙摆或衣服下摆，再回到正面。动作舒缓，每个造型短暂停留，重点展示服装。']
    lines += ['保持衣服款式、图案和装饰稳定，肢体自然，无多余手臂、手指或人物，无脸部漂移、衣服融化、闪烁、字幕、水印或Logo。无对白口播，轻微自然环境声。']
    return '\n\n'.join(lines)
