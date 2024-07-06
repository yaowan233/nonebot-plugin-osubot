import re
from io import BytesIO
from datetime import datetime
from collections import Counter
from statistics import mode, median

from nonebot.log import logger
from PIL import Image, ImageDraw

from ..api import api_info
from ..schema.user import UserCompact
from ..schema.match import Game, Match
from .utils import crop_bg, draw_fillet, open_user_icon, draw_rounded_rectangle
from .static import (
    MpLink,
    TeamRed,
    TeamBlue,
    Torus_SemiBold_20,
    Torus_SemiBold_25,
    Torus_SemiBold_30,
    Torus_SemiBold_40,
    Torus_SemiBold_45,
)


async def draw_rating(match_id: str, algorithm: str = "osuplus") -> bytes:
    match_info = Match(**(await api_info("matches", f"https://osu.ppy.sh/api/v2/matches/{match_id}")))
    pattern = r"([^:]+): [\(\（](.+?)[\)\）] vs [\(\（](.+?)[\)\）]"
    match_name = re.search(pattern, match_info.match["name"], re.IGNORECASE)
    game_history = []
    for sequence in match_info.events:
        if sequence.detail.type == "other" and sequence.game is not None:
            game_history.append(sequence.game)
    # 判断比赛的队伍类型
    team_type_list = []
    invalid_user_list = []
    appeared_user_list = []
    for game in game_history:
        team_type_list.append(game.team_type)
    team_type = mode(team_type_list)
    # 移除无效用户
    for game in game_history:
        for entry in game.scores:
            appeared_user_list.append(entry.user_id)
            if entry.score == 0:
                appeared_user_list.remove(entry.user_id)
                invalid_user_list.append(entry.user_id)
        for entry in game.scores:
            if entry.user_id in invalid_user_list:
                game.scores.remove(entry)
    match_info.users = [user for user in match_info.users if user.id in appeared_user_list]
    # TEAM_VS 模式下，分析比赛历史
    if team_type == "team-vs":
        analyzed_result = analyze_team_vs_game_history(game_history)
        # 移除无效游戏
        for game in game_history:
            if len(game.scores) != analyzed_result["team_size"] * 2:
                game_history.remove(game)

    # 绘制背景
    logger.info("开始绘制比赛历史地图信息")
    im = Image.new(
        "RGBA",
        (2040, 280 + 170 * ((len(match_info.users) - len(invalid_user_list) + 1) // 2) + 90),
        (31, 41, 46, 255),
    )

    draw = ImageDraw.Draw(im)
    im.alpha_composite(MpLink, (0, 0))

    if team_type == "team-vs":
        match_title = match_name.group(1)
        team_red = match_name.group(2)
        team_blue = match_name.group(3)
        text = f"{match_title}:  {team_red} VS {team_blue}"
        draw.text((1020, 130), text, font=Torus_SemiBold_40, anchor="mm")
    elif team_type == "head-to-head":
        match_title = match_info.match["name"]
        draw.text((1020, 130), f"{match_title}", font=Torus_SemiBold_40, anchor="mm")

    # 绘制时间
    draw.text(
        (1020, 220),
        f"{datetime.fromisoformat(match_info.match['start_time']).strftime('%Y-%m-%d %H:%M')} - "
        f"{datetime.fromisoformat(match_info.match['end_time']).strftime('%H:%M')}",
        font=Torus_SemiBold_25,
        anchor="mm",
    )
    # 在底部绘制当前时间
    draw.text(
        (1950, 280 + 170 * ((len(match_info.users) - len(invalid_user_list) + 1) // 2) + 90 - 50),
        f"绘制时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        font=Torus_SemiBold_20,
        anchor="rb",
    )

    player_statistic_list = []
    for i, user in enumerate(match_info.users):
        calculater = PlayerRatingCalculation(match_info)
        rating = calculater.get_rating(user.id, algorithm)
        player_stats = PlayerMatchStats(user, game_history)
        player_statistic_list.append((user, player_stats, rating))

    player_statistic_list.sort(key=lambda x: x[2], reverse=True)

    for i, (user, player_stats, rating) in enumerate(player_statistic_list):
        if player_stats.total_score == 0:
            continue
        if player_stats.player_team == "red":
            fill = "#d32f2e"
            background = TeamRed
        else:
            fill = "#00a0e8"
            background = TeamBlue
        rating_color = rating_to_wn8_hex(rating, player_stats.win_rate)

        # 左右列的判断
        if i % 2 == 0:
            base_y = 170 * (i // 2)
            x_offset = 0
        else:
            base_y = 170 * ((i - 1) // 2)
            x_offset = 1020

        draw_rounded_rectangle(draw, ((140 + x_offset, 280 + base_y), (336 + x_offset, 390 + base_y)), 20, fill=fill)
        draw_rounded_rectangle(
            draw, ((736 + x_offset, 280 + base_y), (966 + x_offset, 389 + base_y)), 20, fill=rating_color[1]
        )
        background = await crop_bg((650, 110), background)
        background = draw_fillet(background, 20)
        im.paste(background, (160 + x_offset, 280 + base_y), background)
        avatar = await open_user_icon(user)
        avatar = await crop_bg((176, 110), avatar)
        avatar = draw_fillet(avatar, 20)
        im.paste(avatar, (160 + x_offset, 280 + base_y), avatar)

        draw.text(
            (40 + x_offset, 335 + base_y),
            f"#{i + 1}",
            font=Torus_SemiBold_40,
            fill="#ffffff",
            anchor="lm",
        )

        draw.text(
            (350 + x_offset, 306 + base_y),
            f"{user.username}",
            font=Torus_SemiBold_30,
            fill="#ffffff",
            anchor="lm",
        )

        draw.text(
            (350 + x_offset, 341 + base_y),
            f"Total Score: {score_to_3digit(player_stats.total_score)}"
            f" ({score_to_3digit(player_stats.average_score)})",
            font=Torus_SemiBold_20,
            fill="#bbbbbb",
            anchor="lm",
        )

        if team_type == "team-vs":
            draw.text(
                (350 + x_offset, 366 + base_y),
                f"Win Rate: {player_stats.win_rate:.2%} ({player_stats.win_and_lose[0]}W"
                f"-{player_stats.win_and_lose[1]}L)",
                font=Torus_SemiBold_20,
                fill="#bbbbbb",
                anchor="lm",
            )
        elif team_type == "head-to-head":
            head_to_head_result = analyze_head_to_head_history(game_history, user.id)
            top1_rate = head_to_head_result["top1_rate"]
            top1_count = head_to_head_result["number_of_games_top1"]
            game_amount = head_to_head_result["number_of_games"]
            draw.text(
                (350 + x_offset, 366 + base_y),
                f"Top 1 Rate: {top1_rate:.2%} ({top1_count} W/{game_amount} P)",
                font=Torus_SemiBold_20,
                fill="#bbbbbb",
                anchor="lm",
            )

        draw.text(
            (840 + x_offset, 340 + base_y),
            f"{rating:.2f}",
            font=Torus_SemiBold_45,
            fill="#ffffff",
            anchor="lm",
        )

    byt = BytesIO()
    im.save(byt, format="PNG")
    im.close()

    return byt.getvalue()


def rating_to_wn8_hex(rating: float, win_rate: float) -> tuple[float, str]:
    # Assuming the rating 2.5 maps linearly to 2900 WN8, create a conversion factor
    rating_to_wn8_factor = 2900 / 2

    # Convert the rating to WN8 using the factor and weight for rating
    wn8_rating = rating * rating_to_wn8_factor * 0.6

    # Add the weighted win rate component (assuming max win rate is 100% equivalent to WN8 2900+)
    wn8_rating += (win_rate / 100) * 2900 * 0.4

    # Define the WN8 ranges and corresponding hex colors from the image
    wn8_ranges_hex_colors = [
        (0, 300, "#871F17"),  # Very Bad
        (300, 449, "#BD413A"),  # Bad
        (450, 649, "#C17E2B"),  # Below Average
        (650, 899, "#C9B93C"),  # Average
        (900, 1199, "#899B3B"),  # Above Average
        (1200, 1599, "#557232"),  # Good
        (1600, 1999, "#5998BC"),  # Very Good
        (2000, 2449, "#4871C1"),  # Great
        (2450, 2899, "#7141AF"),  # Unicum
        (2900, float("inf"), "#3A136B"),  # Super Unicum
    ]

    # Determine the hex color based on the WN8 rating
    for lower_bound, upper_bound, hex_color in wn8_ranges_hex_colors:
        if lower_bound <= int(wn8_rating) <= upper_bound:
            return wn8_rating, hex_color
    return wn8_rating, "#FFFFFF"  # Default color (white) if not found


def score_to_3digit(score: float) -> str:
    if score > 1000000:
        short_score = score / 1000000
        return f"{short_score:.2f}M"
    elif score > 1000:
        short_score = score / 1000
        return f"{short_score:.2f}K"
    return str(score)


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
        "top1_rate": (number_of_games_top1 / number_of_games if number_of_games != 0 else 0),
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


class PlayerRatingCalculation:
    def __init__(self, match_info: Match):
        self._match_info = match_info

    def get_rating(self, user_id: int, algorithm: str = "osuplus"):
        if algorithm == "osuplus":
            return self._osuplus_rating(user_id)
        if algorithm == "bathbot":
            return self._bathbot_rating(user_id)
        if algorithm == "flashlight":
            return self._flashlight_rating(user_id)

        return None

    def _osuplus_rating(self, user_id: int) -> float:
        # 获取比赛中的所有记录
        game_history = []
        for sequence in self._match_info.events:
            if sequence.detail.type == "other" and sequence.game is not None:
                game_history.append(sequence.game)

        # 统计比赛中的数据
        number_of_games = 0
        number_of_games_by_user = 0
        user_scores = []
        average_scores = []

        for i, game in enumerate(game_history):
            if len(game.scores) == 0:
                continue
            number_of_games += 1
            for entry in game.scores:
                user_info = next(
                    (user for user in self._match_info.users if user.id == user_id),
                    (None, None, None),
                )
                if user_info is None:
                    continue
                if entry.user_id == user_id:
                    average_scores.append(sum([entry.score for entry in game.scores]) / len(game.scores))
                    user_scores.append(entry.score)
                    number_of_games_by_user += 1

        # 计算osuplus算法评分
        n_prime = len(user_scores)  # number of games by the player
        sum_of_ratios = sum(s_i / m_i for s_i, m_i in zip(user_scores, average_scores) if m_i != 0)
        cost = (2 / (n_prime + 2)) * sum_of_ratios

        return cost

    def _bathbot_rating(self, user_id: int) -> float:
        # 获取比赛中的所有记录
        game_history = []
        for sequence in self._match_info.events:
            if sequence.detail.type == "other" and sequence.game is not None:
                game_history.append(sequence.game)

        number_of_games = 0
        number_of_games_by_user = 0
        user_tiebreaker_score = 0
        average_tiebreaker_score = 0
        user_scores = []
        average_scores = []
        red_score = 0
        blue_score = 0
        tiebreaker = False
        all_played_mods = set()

        for i, game in enumerate(game_history):
            if len(game.scores) == 0:
                continue
            number_of_games += 1
            # 获取比分
            win_side = get_win_side(game)
            if win_side == "red":
                red_score += 1
            elif win_side == "blue":
                blue_score += 1
            for entry in game.scores:
                user_info = next(
                    (user for user in self._match_info.users if user.id == user_id),
                    (None, None, None),
                )
                if user_info is None:
                    continue
                if entry.user_id == user_id:
                    for mod in entry.mods:
                        all_played_mods.add(mod)
                    average_scores.append(sum([entry.score for entry in game.scores]) / len(game.scores))
                    user_scores.append(entry.score)
                    number_of_games_by_user += 1
            # 获取加时赛数据
            if i == len(game_history) - 2 and red_score == blue_score:
                tiebreaker = True
                average_tiebreaker_score = sum(entry.score for entry in game.scores) / len(game.scores)
                for entry in game.scores:
                    if entry.user_id == user_id:
                        user_tiebreaker_score = entry.score
                        break

        # 计算bathbot算法评分
        score_sum = sum(player_score / avg_score for player_score, avg_score in zip(user_scores, average_scores))
        participation_bonus = number_of_games_by_user * 0.5
        if tiebreaker:
            tiebreaker_bonus = user_tiebreaker_score / average_tiebreaker_score
        else:
            tiebreaker_bonus = 0
        average_factor = 1 / number_of_games_by_user
        participation_bonus_factor = 1.4 ** ((number_of_games_by_user - 1) / (number_of_games - 1)) ** 0.6
        mod_combination_bonus_factor = 1 + 0.02 * max(0, len(all_played_mods) - 2)
        rating = (
            (score_sum + participation_bonus + tiebreaker_bonus)
            * average_factor
            * participation_bonus_factor
            * mod_combination_bonus_factor
        )

        return rating

    def _flashlight_rating(self, user_id: int) -> float:
        # 获取比赛中的所有记录
        game_history = []
        for sequence in self._match_info.events:
            if sequence.detail.type == "other" and sequence.game is not None:
                game_history.append(sequence.game)

        # 统计比赛中的数据
        number_of_games_by_user = 0
        user_scores = []
        median_scores = []
        counts = Counter()

        for i, game in enumerate(game_history):
            if len(game.scores) == 0:
                continue

            for entry in game.scores:
                counts[entry.user_id] += 1
                user_info = next(
                    (user for user in self._match_info.users if user.id == user_id),
                    (None, None, None),
                )
                if user_info is None:
                    continue
                if entry.user_id == user_id:
                    median_scores.append(median([entry.score for entry in game.scores]))
                    user_scores.append(entry.score)
                    number_of_games_by_user += 1

        # 计算中位数
        occurrences = sorted(counts.values(), reverse=True)
        median_of_games_of_all_users = median(occurrences)

        # 计算flashlight算法评分
        sum_of_ratios = sum(N_i / M_i for N_i, M_i in zip(user_scores, median_scores))
        average_ratio = sum_of_ratios / number_of_games_by_user
        adjustment_factor = (number_of_games_by_user / median_of_games_of_all_users) ** (1 / 3)
        match_costs = average_ratio * adjustment_factor

        return match_costs


class PlayerMatchStats:
    def __init__(self, user: UserCompact, game_history: list[Game]):
        self.user = user
        self.game_history = game_history
        self.player_team = self._get_player_team()
        self.win_and_lose = self._get_win_and_lose()
        self.win_rate = self._get_win_rate()
        self.total_score = self._get_total_score()
        self.average_score = self._get_average_score()

    def _get_player_team(self) -> str:
        """
        获取用户所在队伍
        :return: 队伍
        """
        for game in self.game_history:
            for entry in game.scores:
                if entry.user_id == self.user.id:
                    return entry.match["team"]

    def _get_win_and_lose(self) -> tuple:
        """
        获取用户胜利和失败次数
        :return: (胜利次数, 失败次数)
        """
        number_of_wins_by_user = 0
        number_of_games_by_user = 0

        for i, game in enumerate(self.game_history):
            if len(game.scores) == 0:
                continue
            for entry in game.scores:
                if entry.user_id == self.user.id:
                    number_of_games_by_user += 1
                    player_team = entry.match["team"]
                    win_side = get_win_side(game)
                    if player_team == win_side:
                        number_of_wins_by_user += 1

        number_of_loses_by_user = number_of_games_by_user - number_of_wins_by_user
        return number_of_wins_by_user, number_of_loses_by_user, number_of_games_by_user

    def _get_win_rate(self) -> float:
        """
        获取用户胜率
        :return: 胜率
        """
        number_of_wins_by_user = 0
        number_of_games_by_user = 0

        for i, game in enumerate(self.game_history):
            if len(game.scores) == 0:
                continue
            for entry in game.scores:
                if entry.user_id == self.user.id:
                    number_of_games_by_user += 1
                    player_team = entry.match["team"]
                    win_side = get_win_side(game)
                    if player_team == win_side:
                        number_of_wins_by_user += 1

        if number_of_games_by_user == 0:
            return 0
        win_rate = number_of_wins_by_user / number_of_games_by_user
        return win_rate

    def _get_total_score(self) -> int:
        """
        获取用户总分数
        :return: 总分数
        """
        total_score = 0
        for game in self.game_history:
            for entry in game.scores:
                if entry.user_id == self.user.id:
                    total_score += entry.score
        return total_score

    def _get_average_score(self) -> float:
        """
        获取用户平均分数
        :return: 平均分数
        """
        total_score = 0
        number_of_games = 0
        for game in self.game_history:
            for entry in game.scores:
                if entry.user_id == self.user.id:
                    total_score += entry.score
                    number_of_games += 1
        if number_of_games == 0:
            return 0
        average_score = total_score / number_of_games
        return average_score
