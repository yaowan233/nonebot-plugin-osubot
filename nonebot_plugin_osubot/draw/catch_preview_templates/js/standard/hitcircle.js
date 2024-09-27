function HitCircle(data, beatmap)
{
    HitObject.call(this, data, beatmap);

    this.stack = 0;
}
HitCircle.prototype = Object.create(HitObject.prototype, {
    newCombo: {
        get: function()
        {
            return this.flag & 4;
        }
    },
    comboSkip: {
        get: function()
        {
            return this.flag >> 4;
        }
    }
});
HitCircle.prototype.constructor = HitCircle;
HitCircle.ID = 1;
HitCircle.FADE_IN_TIME = 375;
HitCircle.FADE_OUT_TIME = 200;
HitCircle.prototype.draw = function(time, ctx)
{
    var dt = this.time - time,
        opacity = 1;
    if (dt >= 0)
    {
        opacity = (this.beatmap.approachTime - dt) / HitCircle.FADE_IN_TIME;
    }
    else
    {
        opacity = 1 + dt / HitCircle.FADE_OUT_TIME;
    }
    ctx.globalAlpha = Math.max(0, Math.min(opacity, 1));

    this.drawCircle(this.position, ctx);
    this.drawText(this.position, this.combo, 0, ctx);
    if (dt >= 0)
    {
        this.drawApproach(dt, ctx);
    }
};
HitCircle.prototype.drawCircle = function(position, ctx)
{
    // HitCircle
    ctx.beginPath();
    ctx.arc(position.x - this.stack * this.beatmap.stackOffset,
        position.y - this.stack * this.beatmap.stackOffset,
        this.beatmap.circleRadius - this.beatmap.circleBorder / 2, -Math.PI, Math.PI);
    ctx.shadowBlur = 0;
    ctx.fillStyle = this.color;
    ctx.fill();
    // Overlay
    ctx.shadowBlur = this.beatmap.shadowBlur;
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = this.beatmap.circleBorder;
    ctx.stroke();
};
HitCircle.prototype.drawText = function(position, text, deg, ctx)
{
    ctx.shadowBlur = this.beatmap.shadowBlur;
    ctx.fillStyle = '#fff';
    ctx.save();
    ctx.translate(position.x - this.stack * this.beatmap.stackOffset,
        position.y - this.stack * this.beatmap.stackOffset);
    ctx.rotate(deg);
    ctx.fillText(text, 0, 0);
    ctx.restore();
};
HitCircle.prototype.drawApproach = function(dt, ctx)
{
    var scale = 1 + dt / this.beatmap.approachTime * 3;
    ctx.beginPath();
    ctx.arc(this.position.x - this.stack * this.beatmap.stackOffset,
        this.position.y - this.stack * this.beatmap.stackOffset,
        this.beatmap.circleRadius * scale - this.beatmap.circleBorder / 2, -Math.PI, Math.PI);
    ctx.shadowBlur = 0;
    ctx.strokeStyle = this.color;
    ctx.lineWidth = this.beatmap.circleBorder / 2 * scale;
    ctx.stroke();
};
