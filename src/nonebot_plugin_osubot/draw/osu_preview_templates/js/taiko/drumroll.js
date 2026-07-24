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
    var diam = Taiko.DIAMETER * ((this.hitSound & 4) ? 1 / 0.65 : 1);
    var startX = this.beatmap.calcX(this.position.x, scroll);
    var endX = this.beatmap.calcX(this.endPosition.x, scroll, this.position.x);
    var skin = this.beatmap.skin || {};
    var middle = skin['taiko-roll-middle.png'];
    var end = skin['taiko-roll-end.png'];
    if (middle || end)
    {
        if (middle)
        {
            ctx.drawImage(
                middle,
                Math.min(startX, endX),
                -diam / 2,
                Math.abs(endX - startX),
                diam
            );
        }
        if (end)
        {
            ctx.drawImage(end, endX - diam / 2, -diam / 2, diam, diam);
        }
        return;
    }

    var border = 3;

    ctx.beginPath();
    ctx.moveTo(startX, 0);
    ctx.lineTo(endX, 0);

    ctx.strokeStyle = '#333';
    ctx.lineWidth = diam;
    ctx.stroke();

    ctx.strokeStyle = Taiko.DEFAULT_COLORS[2];
    ctx.lineWidth = diam - border;
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(startX, 0, diam / 2 - border / 2, -Math.PI, Math.PI);
    ctx.fillStyle = Taiko.DEFAULT_COLORS[2];
    ctx.fill();
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = border;
    ctx.stroke();
};
