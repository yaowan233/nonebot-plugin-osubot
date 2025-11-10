function HoldNote(data, beatmap)
{
    HitNote.call(this, data, beatmap);

    this.endTime = data[5].split(':')[0] | 0;
}
HoldNote.prototype = Object.create(HitNote.prototype);
HoldNote.prototype.constructor = HoldNote;
HoldNote.ID = 128;
Mania.prototype.hitObjectTypes[HoldNote.ID] = HoldNote;
HoldNote.WIDTH_SCALE = 0.8;
HoldNote.OPACITY = 0.88;
HoldNote.prototype.draw = function(scroll, ctx)
{
    var sy = this.beatmap.calcY(this.position.y, scroll) - Mania.COLUMN_WIDTH / 3,
        ey = this.beatmap.calcY(this.endPosition.y, scroll) - Mania.COLUMN_WIDTH / 3;

    var w = Mania.COLUMN_WIDTH * HoldNote.WIDTH_SCALE;
    ctx.globalAlpha = HoldNote.OPACITY;
    ctx.beginPath();
    ctx.rect(this.position.x + (Mania.COLUMN_WIDTH - w) / 2, ey, w, sy - ey);
    ctx.fillStyle = this.color;
    ctx.fill();
    ctx.globalAlpha = 1;

    ctx.beginPath();
    ctx.rect(this.position.x, sy, Mania.COLUMN_WIDTH, Mania.COLUMN_WIDTH / 3);
    ctx.fill();
    ctx.strokeStyle = '#ccc';
    ctx.lineWidth = 1;
    ctx.stroke();

    ctx.beginPath();
    ctx.rect(this.position.x, ey, Mania.COLUMN_WIDTH, Mania.COLUMN_WIDTH / 3);
    ctx.fill();
    ctx.stroke();
};
