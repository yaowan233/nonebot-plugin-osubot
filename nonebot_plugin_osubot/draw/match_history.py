import re
from datetime import datetime
from io import BytesIO
from statistics import mode

from PIL import Image, ImageDraw, ImageEnhance
from nonebot import logger

from .static import (
    Torus_SemiBold_40,
    Torus_SemiBold_50,
    Torus_SemiBold_25,
    Torus_SemiBold_20,
    Torus_SemiBold_30,
    Torus_Regular_25,
    Torus_Regular_20,
    TeamRed,
    TeamBlue,
    MpLink,
    MpLinkMap,
    osufile,
)
from .utils import draw_fillet, stars_diff, open_user_icon, crop_bg
from ..api import get_map_bg, api_info
from ..file import map_path, download_osu, re_map
from ..pp import cal_old_pp
from ..schema import Score, Match, Game


async def draw_match_history(match_id: str) -> bytes:
    match_info = Match(
        **(await api_info("matches", f"https://osu.ppy.sh/api/v2/matches/{match_id}"))
    )
    pattern = r"([^:]+): [\(\（](.+?)[\)\）] vs [\(\（](.+?)[\)\）]"
    match_name = re.search(pattern, match_info.match["name"], re.IGNORECASE)
    game_history = []
    for sequence in match_info.events:
        if sequence.detail.type == "other" and sequence.game is not None:
            game_history.append(sequence.game)

    analyzed_game_history = analyze_team_vs_game_history(game_history)

    number_of_invalid_records = 0
    for game in game_history:
        if len(game.scores) == 0:
            number_of_invalid_records += 1

    # 判断比赛的队伍类型
    team_type_list = []
    invalid_user_list = []
    for game in game_history:
        team_type_list.append(game.team_type)
    team_type = mode(team_type_list)
    # TEAM_VS 模式下，分析比赛历史
    if team_type == "team-vs":
        analyzed_result = analyze_team_vs_game_history(game_history)
        # 移除无效用户
        for game in game_history:
            for entry in game.scores:
                if entry.score == 0:
                    invalid_user_list.append(entry.user_id)
            for entry in game.scores:
                if entry.user_id in invalid_user_list:
                    game.scores.remove(entry)
        # 移除无效游戏
        for game in game_history:
            if len(game.scores) != analyzed_result["team_size"] * 2:
                game_history.remove(game)

    # 绘制背景
    logger.info("开始绘制比赛历史地图信息")
    im = Image.new(
        "RGBA", (1420, 280 + (280 * (len(game_history)) + 90)), (31, 41, 46, 255)
    )
    draw = ImageDraw.Draw(im)
    im.alpha_composite(MpLink, (0, 0))
    # 绘制标题
    if match_name:
        match_title = match_name.group(1)
        team_red = match_name.group(2)
        team_blue = match_name.group(3)
        draw.text((710, 120), "VS", font=Torus_SemiBold_40, anchor="mm")
        draw.text(
            (675, 120),
            f"{match_title}:  {team_red}",
            font=Torus_SemiBold_40,
            anchor="rm",
        )
        draw.text((745, 120), f"{team_blue}", font=Torus_SemiBold_40, anchor="lm")
    # 绘制比分
    red_score = analyzed_game_history["red_score"]
    blue_score = analyzed_game_history["blue_score"]
    draw.text(
        (690, 180),
        f"{red_score}",
        font=Torus_SemiBold_50,
        anchor="rm",
    )
    draw.text(
        (710, 180),
        ":",
        font=Torus_SemiBold_50,
        anchor="mm",
    )
    draw.text(
        (730, 180),
        f"{blue_score}",
        font=Torus_SemiBold_50,
        anchor="lm",
    )
    # 绘制时间
    draw.text(
        (1400, 260),
        f"{datetime.fromisoformat(match_info.match['start_time']).strftime('%Y-%m-%d %H:%M')} - "
        f"{datetime.fromisoformat(match_info.match['end_time']).strftime('%H:%M')}",
        font=Torus_SemiBold_25,
        anchor="rb",
    )
    # 在底部绘制当前时间
    draw.text(
        (1400, 280 * (len(game_history)) + 280 + 50),
        f"绘制时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        font=Torus_SemiBold_20,
        anchor="rb",
    )

    # 绘制比赛信息
    number_of_invalid_records = 0
    total_stars = 0
    for i, game in enumerate(game_history):
        if len(game.scores) == 0:
            number_of_invalid_records += 1
            continue
        sequence = i - number_of_invalid_records
        logger.info(f"开始绘制第{sequence + 1}局")
        im.alpha_composite(MpLinkMap, (0, 280 * sequence + 280))
        # 获取地图
        map_info = game.beatmap
        # 绘制bg
        if not map_info:
            logger.error(f"第{sequence + 1}局地图信息为空")
            continue
        path = map_path / str(map_info.beatmapset_id)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
        osu = path / f"{map_info.id}.osu"
        if not osu.exists():
            await download_osu(map_info.beatmapset_id, map_info.id)
        pp_info = cal_old_pp(game.scores[0], str(osu.absolute()))

        # 计算分差
        scores = game.scores
        total_score_red = 0
        total_score_blue = 0

        for entry in scores:
            if entry.match["team"] == "red":
                total_score_red += entry.score
            elif entry.match["team"] == "blue":
                total_score_blue += entry.score

        score_diff = total_score_red - total_score_blue
        draw.text(
            (710, 280 * sequence + 280 + 230),
            f"分差: {score_diff:,}",
            font=Torus_SemiBold_25,
            anchor="mm",
        )
        # 绘制地图胜利方
        win_side = get_win_side(game)
        if win_side == "red":
            im.alpha_composite(TeamRed, (288, 280 * sequence + 280 + 36))
        elif win_side == "blue":
            im.alpha_composite(TeamBlue, (838, 280 * sequence + 280 + 36))
        gutter = 570 // (analyzed_game_history["team_size"] + 1)
        # 获取top3分数
        top3 = get_top3(game.scores)
        # 绘制玩家分数以及头像
        # 红队
        slot = 0
        score_img = Image.new("RGBA", (550, 215), (205, 205, 205, 0))
        score_draw = ImageDraw.Draw(score_img)
        for entry in game.scores:
            if entry.match["team"] == "blue":
                continue
            user_id = entry.user_id
            user_info = next(
                (user for user in match_info.users if user.id == user_id),
                (None, None, None),
            )
            if user_info is None:
                continue
            # 如果是top3则在头像上圆形颜色背景以及名次
            if (user_id, entry.score) in top3:
                color = get_top3_color(top3.index((user_id, entry.score)) + 1)
                left = (slot + 1) * gutter - 15
                top = 10
                right = left + 30
                bottom = top + 30
                score_draw.ellipse([left, top, right, bottom], fill=color)
                score_draw.text(
                    ((slot + 1) * gutter, 25),
                    f"{top3.index((user_id, entry.score)) + 1}",
                    font=Torus_SemiBold_20,
                    anchor="mm",
                    fill="black",
                )
            # 绘制头像
            user_icon = await open_user_icon(user_info)
            user_icon = user_icon.convert("RGBA").resize((60, 60))
            user_icon = draw_fillet(user_icon, 10)
            score_img.alpha_composite(user_icon, ((slot + 1) * gutter - 30, 45))
            # 绘制用户名
            score_draw.text(
                ((slot + 1) * gutter, 120),
                f"{user_info.username}",
                font=Torus_Regular_20,
                anchor="mm",
            )
            # 绘制分数
            score_draw.text(
                ((slot + 1) * gutter, 145),
                f"{entry.score:,}",
                font=Torus_Regular_20,
                anchor="mm",
            )
            # 绘制ACC
            score_draw.text(
                ((slot + 1) * gutter, 170),
                f"{entry.accuracy * 100:.2f}%",
                font=Torus_Regular_20,
                anchor="mm",
            )
            # 绘制mods
            if "NF" in entry.mods:
                entry.mods.remove("NF")
            for mods_num, s_mods in enumerate(entry.mods):
                mods_bg = osufile / "mods" / f"{s_mods}.png"
                mods_img = Image.open(mods_bg).convert("RGBA").resize((30, 18))
                score_img.alpha_composite(
                    mods_img, ((slot + 1) * gutter + 32 * mods_num - 40, 185)
                )
            slot += 1
        im.alpha_composite(score_img, (10, 280 * sequence + 280 + 35))
        score_img.close()

        # 蓝队
        slot = 0
        score_img = Image.new("RGBA", (550, 215), (205, 205, 205, 0))
        score_draw = ImageDraw.Draw(score_img)
        for entry in game.scores:
            if entry.match["team"] == "red":
                continue
            user_id = entry.user_id
            user_info = next(
                (user for user in match_info.users if user.id == user_id),
                (None, None, None),
            )
            if user_info is None:
                continue

            # 如果是top3则在头像上绘制圆形颜色背景以及名次
            if (user_id, entry.score) in top3:
                color = get_top3_color(top3.index((user_id, entry.score)) + 1)
                left = (slot + 1) * gutter - 15
                top = 10
                right = left + 30
                bottom = top + 30
                score_draw.ellipse([left, top, right, bottom], fill=color)
                score_draw.text(
                    ((slot + 1) * gutter, 25),
                    f"{top3.index((user_id, entry.score)) + 1}",
                    font=Torus_SemiBold_20,
                    anchor="mm",
                    fill="black",
                )
            # 绘制头像
            user_icon = await open_user_icon(user_info)
            user_icon = user_icon.convert("RGBA").resize((60, 60))
            user_icon = draw_fillet(user_icon, 10)
            score_img.alpha_composite(user_icon, ((slot + 1) * gutter - 30, 45))
            # 绘制用户名
            score_draw.text(
                ((slot + 1) * gutter, 120),
                f"{user_info.username}",
                font=Torus_Regular_20,
                anchor="mm",
            )
            # 绘制分数
            score_draw.text(
                ((slot + 1) * gutter, 145),
                f"{entry.score:,}",
                font=Torus_Regular_20,
                anchor="mm",
            )
            # 绘制ACC
            score_draw.text(
                ((slot + 1) * gutter, 170),
                f"{entry.accuracy * 100:.2f}%",
                font=Torus_Regular_20,
                anchor="mm",
            )
            # 绘制mods
            if "NF" in entry.mods:
                entry.mods.remove("NF")
            for mods_num, s_mods in enumerate(entry.mods):
                mods_bg = osufile / "mods" / f"{s_mods}.png"
                mods_img = Image.open(mods_bg).convert("RGBA").resize((30, 18))
                score_img.alpha_composite(
                    mods_img, ((slot + 1) * gutter - 40 + 32 * mods_num, 190)
                )
            slot += 1
        im.alpha_composite(score_img, (830, 280 * sequence + 280 + 35))
        cover = re_map(osu)
        cover_path = path / cover
        if not cover_path.exists():
            if bg := await get_map_bg(map_info.id, map_info.beatmapset_id, cover):
                with open(cover_path, "wb") as f:
                    f.write(bg.getvalue())
        cropped_bg = await crop_bg("H", cover_path)
        rounded_bg = draw_fillet(cropped_bg, 20)
        enhanced_bg = ImageEnhance.Brightness(rounded_bg).enhance(0.5)
        im.alpha_composite(enhanced_bg, (590, 280 * sequence + 280 + 40))
        # 绘制地图信息
        map_title = f"{game.beatmap.beatmapset.title}"
        text_width = draw.textlength(map_title, font=Torus_SemiBold_30)
        if text_width > 200:
            for t in range(1, len(map_title)):
                if draw.textlength(map_title[:t], font=Torus_SemiBold_30) > 200:
                    map_title = map_title[: t - 1] + "..."
                    break
        draw.text(
            (600, 280 * sequence + 325),
            f"{map_title}",
            font=Torus_SemiBold_30,
            anchor="lt",
        )
        artist = f"{game.beatmap.beatmapset.artist}"
        text_width = draw.textlength(artist, font=Torus_Regular_20)
        if text_width > 180:
            for t in range(1, len(artist)):
                if draw.textlength(artist[:t], font=Torus_Regular_20) > 180:
                    artist = artist[: t - 1] + "..."
                    break
        draw.text(
            (600, 280 * sequence + 357),
            f"{artist}",
            font=Torus_Regular_20,
            anchor="lt",
        )
        diff = f"{game.beatmap.version}"
        text_width = draw.textlength(diff, font=Torus_Regular_20)
        if text_width > 180:
            for t in range(1, len(diff)):
                if draw.textlength(diff[:t], font=Torus_Regular_20) > 180:
                    diff = diff[: t - 1] + "..."
                    break
        draw.text(
            (600, 280 * sequence + 380),
            f"{diff}",
            font=Torus_Regular_20,
            anchor="lt",
        )
        beatmap_id = f"{game.beatmap.id}"
        draw.text(
            (820, 280 * sequence + 415),
            f"b{beatmap_id}",
            font=Torus_SemiBold_20,
            anchor="rt",
        )
        # 难度星数
        stars = pp_info.difficulty.stars
        total_stars += stars
        stars_img = stars_diff(stars)
        stars_img = stars_img.resize((90, 36))
        im.alpha_composite(stars_img, (670, 280 * sequence + 280 + 167))
        if stars < 6.5:
            color = (0, 0, 0, 255)
        else:
            color = (255, 217, 102, 255)
        draw.text(
            (717, 280 * sequence + 280 + 175),
            f"{stars:.2f}★",
            font=Torus_Regular_25,
            anchor="mt",
            color=color,
        )

    avg_stars = total_stars / (len(game_history) - number_of_invalid_records)
    draw.text(
        (1400, 220),
        f"AVG SR: {avg_stars:.2f}",
        font=Torus_SemiBold_30,
        anchor="rm",
    )

    byt = BytesIO()
    im.convert("RGB").save(byt, "jpeg")
    im.close()

    return byt.getvalue()


def analyze_team_vs_game_history(game_history: list[Game]) -> dict:
    red_score = 0
    blue_score = 0
    team_size_list = []
    for game in game_history:
        # 获取比分
        win_side = get_win_side(game)
        if win_side == "red":
            red_score += 1
        elif win_side == "blue":
            blue_score += 1
        # 获取队伍大小
        team_red_size = 0
        team_blue_size = 0
        for entry in game.scores:
            if entry.score == 0:
                continue
            if entry.match["team"] == "red":
                team_red_size += 1
            elif entry.match["team"] == "blue":
                team_blue_size += 1
        if team_red_size == team_blue_size and team_red_size != 0:
            team_size_list.append(team_red_size)

    analyze_result = {
        "red_score": red_score,
        "blue_score": blue_score,
        "team_size": mode(team_size_list),  # 从 TeamSize 中获取众数, 即队伍大小
    }
    return analyze_result


def analyze_head_to_head_history(game_history: list[Game], user_id: int) -> dict:
    number_of_games = 0
    number_of_games_top1 = 0
    # 获取用户上场次数
    for i, game in enumerate(game_history):
        if len(game.scores) == 0:
            continue
        max_score_obj = max(game.scores, key=lambda x: x.score)
        for entry in game.scores:
            if entry.user_id == user_id:
                number_of_games += 1
        if max_score_obj.user_id == user_id:
            number_of_games_top1 += 1

    analyze_result = {
        "number_of_games": number_of_games,
        "number_of_games_top1": number_of_games_top1,
        "top1_rate": number_of_games_top1 / number_of_games
        if number_of_games != 0
        else 0,
    }
    return analyze_result


def get_win_side(game: Game) -> str:
    scores = game.scores
    total_score_red = 0
    total_score_blue = 0

    for entry in scores:
        if entry.match["team"] == "red":
            total_score_red += entry.score
        elif entry.match["team"] == "blue":
            total_score_blue += entry.score

    if total_score_red > total_score_blue:
        win_side = "red"
    else:
        win_side = "blue"

    return win_side


def get_top3(scores: list[Score]) -> list:
    top3 = []
    for entry in scores:
        top3.append((entry.user_id, entry.score))
    top3 = sorted(top3, key=lambda x: x[1], reverse=True)
    return top3[:3]


def get_top3_color(value: int) -> str:
    if value == 1:
        return "gold"
    elif value == 2:
        return "silver"
    elif value == 3:
        return "#cd7f32"
    else:
        return "white"
