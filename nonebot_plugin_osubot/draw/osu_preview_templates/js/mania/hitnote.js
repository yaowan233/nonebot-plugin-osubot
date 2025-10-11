function HitNote(data, beatmap)
{
    HitObject.call(this, data, beatmap);

    this.column = Math.max(1, Math.min((this.position.x / this.beatmap.columnSize + 1) | 0, this.beatmap.keyCount)) - 1;
}
HitNote.prototype = Object.create(HitObject.prototype);
HitNote.prototype.constructor = HitNote;
HitNote.ID = 1;
Mania.prototype.hitObjectTypes[HitNote.ID] = HitNote;
HitNote.prototype.draw = function(scroll, ctx)
{
    ctx.beginPath();
    ctx.rect(this.position.x, this.beatmap.calcY(this.position.y, scroll) - Mania.COLUMN_WIDTH / 3,
        Mania.COLUMN_WIDTH, Mania.COLUMN_WIDTH / 3);
    ctx.fillStyle = this.color;
    ctx.fill();
    ctx.strokeStyle = '#ccc';
    ctx.lineWidth = 1;
    ctx.stroke();
};
