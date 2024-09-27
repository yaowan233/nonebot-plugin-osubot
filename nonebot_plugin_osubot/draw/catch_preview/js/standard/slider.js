function Slider(data, beatmap)
{
    HitCircle.call(this, data, beatmap);

    var points = data[5].split('|');
    var sliderType = points[0];
    points[0] = this.position;
    for (var i = 1; i < points.length; i++)
    {
        points[i] = new Point(points[i].split(':'));
    }
    this.repeat = data[6] | 0;
    this.pixelLength = +data[7];

    var sliderTime = this.beatmap.timingPointAt(this.time).beatLength * (
            this.pixelLength / this.beatmap.SliderMultiplier
        ) / 100;
    this.endTime += sliderTime * this.repeat;
    this.duration = this.endTime - this.time;

    this.curve = Curve.parse(sliderType, points, this.pixelLength);

    this.endPosition = this.curve.pointAt(1);
}
Slider.prototype = Object.create(HitCircle.prototype);
Slider.prototype.constructor = Slider;
Slider.ID = 2;
Slider.FADE_IN_TIME = 375;
Slider.FADE_OUT_TIME = 200;
Slider.REVERSE_ARROW = String.fromCharCode(10132);
Slider.OPACITY = 0.66;
Slider.prototype.draw = function(time, ctx)
{
    var dt = this.time - time,
        opacity = 1;
    if (dt >= 0)
    {
        opacity = (this.beatmap.approachTime - dt) / Slider.FADE_IN_TIME;
    }
    else if (time > this.endTime)
    {
        opacity = 1 - (time - this.endTime) / Slider.FADE_OUT_TIME;
    }
    ctx.globalAlpha = Math.max(0, Math.min(opacity, 1));

    this.drawPath(ctx);
    // this.drawCircle(this.endPosition, ctx);
    // this.drawCircle(this.position, ctx);

    var repeat = -dt * this.repeat / this.duration;
    //                                   this.repeat - this.repeat % 2: 홀수면 짝수로 내리기
    if (this.repeat > 1 && repeat + 1 <= (this.repeat & ~1))
    {
        this.drawCircle(this.endPosition, ctx);
        this.drawText(this.endPosition, Slider.REVERSE_ARROW, this.curve.endAngle, ctx);
    }
    //                              this.repeat - (this.repeat + 1) % 2: 짝수면 홀수로 내리기
    if (repeat > 0 && repeat + 1 <= this.repeat - !(this.repeat & 1))
    {
        this.drawCircle(this.position, ctx);
        this.drawText(this.position, Slider.REVERSE_ARROW, this.curve.startAngle, ctx);
    }
    else if (dt >= 0)
    {
        this.drawCircle(this.position, ctx);
        this.drawText(this.position, this.combo, 0, ctx);
    }

    if (dt >= 0)
    {
        this.drawApproach(dt, ctx);
    }
    else if (time < this.endTime)
    {
        this.drawFollowCircle(repeat, ctx);
    }
};
Slider.prototype.drawPath = function(ctx)
{
    ctx.save();
    // Slider
    ctx.globalAlpha *= Slider.OPACITY;
    ctx.beginPath();
    ctx.moveTo(this.position.x - this.stack * this.beatmap.stackOffset,
        this.position.y - this.stack * this.beatmap.stackOffset);
    for (var i = 1; i < this.curve.path.length; i++)
    {
        ctx.lineTo(this.curve.path[i].x - this.stack * this.beatmap.stackOffset,
            this.curve.path[i].y - this.stack * this.beatmap.stackOffset);
    }
    ctx.shadowBlur = 0;
    ctx.strokeStyle = this.color;
    ctx.lineWidth = (this.beatmap.circleRadius - this.beatmap.circleBorder) * 2;
    ctx.stroke();
    // Border
    ctx.globalCompositeOperation = 'destination-over';
    ctx.shadowBlur = 0;
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = this.beatmap.circleRadius * 2;
    ctx.stroke();
    ctx.restore();
};
Slider.prototype.drawFollowCircle = function(repeat, ctx)
{
    repeat %= 2;
    if (repeat > 1)
    {
        repeat = 2 - repeat;
    }
    var point = this.curve.pointAt(repeat);
    ctx.beginPath();
    ctx.arc(point.x - this.stack * this.beatmap.stackOffset,
        point.y - this.stack * this.beatmap.stackOffset,
        this.beatmap.circleRadius - this.beatmap.circleBorder / 2, -Math.PI, Math.PI);
    ctx.shadowBlur = this.beatmap.shadowBlur;
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = this.beatmap.circleBorder;
    ctx.stroke();
}
