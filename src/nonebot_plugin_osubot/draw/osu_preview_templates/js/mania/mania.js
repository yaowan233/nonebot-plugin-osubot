function Mania(osu)
{
    Scroll.call(this, osu);


    this.scrollSpeed = Mania.SCROLL_SPEED;
    //this.columnStart = Mania.COLUMN_START;
    this.columnStart = (Beatmap.WIDTH - Mania.COLUMN_WIDTH * this.keyCount) / 2

    for (var i = 0; i < this.keyCount; i++)
    {
        this.Colors[i] = Mania.DEFAULT_COLORS[i & 1];
    }
    var p = this.keyCount / 2;
    if (this.keyCount & 1)
    {
        this.Colors[p | 0] = Mania.DEFAULT_COLORS[2];
    }
    else
    {
        this.Colors = this.Colors.slice(0, p).concat(this.Colors.slice(p - 1));
    }


    for (var i = 0; i < this.HitObjects.length; i++)
    {
        var hitObject = this.HitObjects[i];
        hitObject.color = this.Colors[hitObject.column];
        hitObject.position.x = Mania.COLUMN_WIDTH * hitObject.column;
        hitObject.position.y = this.scrollAt(hitObject.time);
        hitObject.endPosition.y = this.scrollAt(hitObject.endTime);
    }
}
Mania.prototype = Object.create(Scroll.prototype, {
    keyCount: {
        get: function()
        {
            return this.CircleSize;
        }
    },
    columnSize: {
        get: function()
        {
            return Beatmap.MAX_X / this.keyCount;
        }
    }
});
Mania.prototype.constructor = Mania;
Mania.prototype.hitObjectTypes = {};
Mania.ID = 3;
Beatmap.modes[Mania.ID] = Mania;
Mania.DEFAULT_COLORS = [
    '#5bf',
    '#ccc',
    '#da2'
];
Mania.COLUMN_START = 130;
Mania.HIT_POSITION = 400;
Mania.COLUMN_WIDTH = 30;
let savedSpeed = window.localStorage.getItem("SCROLL_SPEED");
Mania.SCROLL_SPEED = (savedSpeed) ? parseInt(savedSpeed) : 20;
Mania.prototype.calcY = function(y, scroll)
{
    return Mania.HIT_POSITION - (y - scroll) * this.scrollSpeed * 0.035;
};
Mania.prototype.update = function(ctx)
{
    ctx.translate(this.columnStart, 0);
};
Mania.prototype.draw = function(time, ctx)
{
    if (typeof this.tmp.first == 'undefined')
    {
        this.tmp.first = 0;
        this.tmp.last = -1;
        this.tmp.barLine = 0;
    }

    var scroll = this.scrollAt(time);
    while (this.tmp.first < this.HitObjects.length &&
        time > this.HitObjects[this.tmp.first].endTime)
    {
        this.tmp.first++;
    }
    while (this.tmp.last + 1 < this.HitObjects.length)
    {
        var hitObject = this.HitObjects[this.tmp.last + 1];
        if (this.calcY(hitObject.position.y, scroll) < -Mania.COLUMN_WIDTH)
        {
            break;
        }
        this.tmp.last++;
    }
    while (this.tmp.barLine < this.barLines.length &&
        this.calcY(this.barLines[this.tmp.barLine], scroll) > Beatmap.MAX_Y)
    {
        this.tmp.barLine++;
    }
    for (var i = this.tmp.barLine; i < this.barLines.length && this.calcY(this.barLines[i], scroll) > -Mania.COLUMN_WIDTH; i++)
    {
        var barLine = this.calcY(this.barLines[i], scroll);
        ctx.beginPath();
        ctx.moveTo(0, barLine);
        ctx.lineTo(Mania.COLUMN_WIDTH * this.keyCount, barLine);
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 1;
        ctx.stroke();
    }
    for (var i = this.tmp.first; i <= this.tmp.last; i++)
    {
        var hitObject = this.HitObjects[i];
        if (time > hitObject.endTime)
        {
            continue;
        }
        hitObject.draw(scroll, ctx);
    }
    ctx.clearRect(0, Mania.HIT_POSITION, Beatmap.WIDTH, Beatmap.HEIGHT - Mania.HIT_POSITION);
};
Mania.prototype.processBG = function(ctx)
{
    ctx.beginPath();
    ctx.rect(0, 0, Mania.COLUMN_WIDTH * this.keyCount, Beatmap.HEIGHT);
    ctx.strokeStyle = '#ddd';
    ctx.lineWidth = 8;
    ctx.stroke();
    ctx.fillStyle = '#000';
    ctx.fill();

    for (var i = 0; i < this.keyCount; i++)
    {
        var x = Mania.COLUMN_WIDTH * i;

        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, Mania.HIT_POSITION);
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 1;
        ctx.stroke();

        ctx.beginPath();
        ctx.rect(x, Mania.HIT_POSITION, Mania.COLUMN_WIDTH, Beatmap.HEIGHT - Mania.HIT_POSITION);
        ctx.fillStyle = this.Colors[i];
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 3;
        ctx.stroke();
    }
    var x = Mania.COLUMN_WIDTH * this.keyCount;
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, Mania.HIT_POSITION);
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 1;
    ctx.stroke();
    // HIT POSITION
    ctx.beginPath();
    ctx.rect(0, Mania.HIT_POSITION, Mania.COLUMN_WIDTH * this.keyCount, Mania.COLUMN_WIDTH / 3);
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.fillStyle = '#568';
    ctx.fill();
};
