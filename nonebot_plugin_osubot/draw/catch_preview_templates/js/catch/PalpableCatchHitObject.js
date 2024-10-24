function PalpableCatchHitObject(data, beatmap) {
    this.beatmap = beatmap;
    this.type = data.type;
    this.time = data.time;
    this.x = data.x;
    this.color = data.color;
    this.radius = data.radius;
    this.hyperDash = false;
}
PalpableCatchHitObject.prototype.draw = function (time, ctx) {
    var dt = this.time - time;
    if (dt >= -this.beatmap.FALLOUT_TIME) {
        if (this.type === "Banana") this.drawBanana({ x: this.x, y: (1 - dt / this.beatmap.approachTime) * Beatmap.HEIGHT - this.beatmap.CATCHER_HEIGHT }, ctx);
        else {
            if (this.hyperDash) this.drawDashCircle({ x: this.x, y: (1 - dt / this.beatmap.approachTime) * Beatmap.HEIGHT - this.beatmap.CATCHER_HEIGHT }, ctx);
            this.drawCircle({ x: this.x, y: (1 - dt / this.beatmap.approachTime) * Beatmap.HEIGHT - this.beatmap.CATCHER_HEIGHT }, ctx);
        }
    }
};
PalpableCatchHitObject.prototype.draw2 = function (obj, SCALE, ctx, BORDER_WIDTH, BORDER_HEIGHT, combo = null) {
    if (obj.type === "Banana") this.drawBanana2({ x: obj.x + BORDER_WIDTH, y: obj.y + BORDER_HEIGHT }, SCALE, ctx);
    else {
        if (this.hyperDash) this.drawDashCircle2({ x: obj.x + BORDER_WIDTH, y: obj.y + BORDER_HEIGHT }, SCALE, ctx);
        this.drawCircle2({ x: obj.x + BORDER_WIDTH, y: obj.y + BORDER_HEIGHT }, SCALE, ctx);
    }
    if (combo) this.drawCombo2({ x: obj.x + BORDER_WIDTH, y: obj.y + BORDER_HEIGHT }, SCALE, combo, ctx);
}
PalpableCatchHitObject.prototype.predraw2 = function (SCREENSHEIGHT, COLMARGIN, SCALE, offset) {
    // 去除offset
    let dt = this.time - offset;
    let real_x = this.x + COLMARGIN / SCALE;
    let real_y = SCREENSHEIGHT - dt * Beatmap.HEIGHT / this.beatmap.approachTime;
    let colIndex = 1;
    while (real_y < 0) {
        colIndex += 1;
        real_x = this.x + Beatmap.WIDTH * (colIndex - 1) + COLMARGIN * (2 * colIndex - 1) / SCALE;
        real_y = SCREENSHEIGHT + real_y;
    }
    // 因为屏幕宽度640，谱面宽度512，所以需要加上Padding = (Beatmap.WIDTH - Beatmap.MAX_X) / 2 = (640-512)/2 = 64
    real_x += 64;
    // 整体缩小
    real_x *= SCALE;
    real_y *= SCALE;
    return { type: this.type, x: real_x, y: real_y, col: colIndex };
}
PalpableCatchHitObject.prototype.drawCircle = function (position, ctx) {
    ctx.save();
    ctx.beginPath();
    ctx.arc(position.x, position.y, this.radius, -Math.PI, Math.PI);
    ctx.shadowBlur = 0;
    ctx.fillStyle = this.color;
    ctx.fill();
    ctx.restore();
};
PalpableCatchHitObject.prototype.drawCircle2 = function (position, SCALE, ctx) {
    ctx.save();
    ctx.beginPath();
    ctx.arc(position.x, position.y, this.radius * SCALE, -Math.PI, Math.PI);
    ctx.shadowBlur = 0;
    ctx.fillStyle = this.color;
    ctx.fill();
    ctx.restore();
    // 边缘白框
    ctx.save();
    ctx.beginPath();
    ctx.shadowBlur = 0;
    ctx.arc(position.x, position.y, this.radius * 0.9 * SCALE, -Math.PI, Math.PI);
    ctx.lineWidth = this.radius * 0.2 * SCALE;
    ctx.strokeStyle = 'white';
    ctx.stroke();
    ctx.restore();
};
PalpableCatchHitObject.prototype.drawCombo2 = function (position, SCALE, combo, ctx) {
    ctx.save();
    ctx.fillStyle = 'lightblue';
    ctx.font = "normal 16px 'Segoe UI'";
    ctx.textBaseline = "middle";
    ctx.textAlign = "start";
    ctx.fillText("x" + combo, position.x + this.radius * SCALE * 2, position.y);
    ctx.restore();
};
PalpableCatchHitObject.prototype.drawBanana = function (position, ctx) {
    ctx.save();
    ctx.beginPath();
    ctx.shadowBlur = 0;
    ctx.arc(position.x, position.y, this.radius * 0.9, -Math.PI, Math.PI);
    ctx.lineWidth = this.radius * 0.2;
    ctx.strokeStyle = this.color;
    ctx.stroke();
    ctx.restore();
};
PalpableCatchHitObject.prototype.drawBanana2 = function (position, SCALE, ctx) {
    ctx.save();
    ctx.beginPath();
    ctx.shadowBlur = 0;
    ctx.arc(position.x, position.y, this.radius * 0.9 * SCALE, -Math.PI, Math.PI);
    ctx.lineWidth = this.radius * 0.2 * SCALE;
    ctx.strokeStyle = this.color;
    ctx.stroke();
    ctx.restore();
};
PalpableCatchHitObject.prototype.drawDashCircle = function (position, ctx) {
    ctx.save();
    ctx.beginPath();
    ctx.shadowBlur = 0;
    ctx.arc(position.x, position.y, this.radius * 1.1, -Math.PI, Math.PI);
    ctx.lineWidth = this.radius * 0.2;
    ctx.strokeStyle = 'rgb(255,0,0)';
    ctx.stroke();
    ctx.restore();
};
PalpableCatchHitObject.prototype.drawDashCircle2 = function (position, SCALE, ctx) {
    ctx.save();
    ctx.beginPath();
    ctx.shadowBlur = 0;
    ctx.arc(position.x, position.y, this.radius * 1.3 * SCALE, -Math.PI, Math.PI);
    ctx.lineWidth = this.radius * 0.6 * SCALE;
    ctx.strokeStyle = 'rgb(255,0,0)';
    ctx.stroke();
    ctx.restore();
};