function Drumroll(data, beatmap)
{
    Slider.call(this, data, beatmap);

}
Drumroll.prototype = Object.create(Slider.prototype, {});
Drumroll.prototype.constructor = Drumroll;
Drumroll.ID = 2;
Taiko.prototype.hitObjectTypes[Drumroll.ID] = Drumroll;
Drumroll.prototype.draw = function(scroll, ctx)
{
    var diam = Taiko.DIAMETER;
    var border = 3;

    ctx.beginPath();
    ctx.moveTo(this.beatmap.calcX(this.position.x, scroll), 0);
    ctx.lineTo(this.beatmap.calcX(this.endPosition.x, scroll), 0);

    ctx.strokeStyle = '#333';
    ctx.lineWidth = diam;
    ctx.stroke();

    ctx.strokeStyle = Taiko.DEFAULT_COLORS[2];
    ctx.lineWidth = diam - border;
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(this.beatmap.calcX(this.position.x, scroll), 0, diam / 2 - border / 2, -Math.PI, Math.PI);
    ctx.fillStyle = Taiko.DEFAULT_COLORS[2];
    ctx.fill();
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = border;
    ctx.stroke();
};
