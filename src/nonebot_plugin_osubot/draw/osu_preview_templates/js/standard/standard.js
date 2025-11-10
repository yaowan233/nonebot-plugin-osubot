function Standard(osu)
{
    Beatmap.call(this, osu);

    let savedDefaultColor = window.localStorage.getItem("DefaultColor");
    this.useDefaultColor = (savedDefaultColor) ? parseInt(savedDefaultColor) : 0;

    let savedColorChange = window.localStorage.getItem("ColorChange");
    this.colorChange = (savedColorChange) ? parseInt(savedColorChange) : 0;

    if (this.Colors.length && !this.useDefaultColor) {
        this.Colors.push(this.Colors.shift());
    }
    else
    {
        this.Colors = Standard.DEFAULT_COLORS;
    }

    var combo = 1,
        comboIndex = -1,
        setComboIndex = 1;
    for (var i = 0; i < this.HitObjects.length; i++)
    {
        var hitObject = this.HitObjects[i];
        if (hitObject instanceof Spinner)
        {
            setComboIndex = 1;
        }
        else if (hitObject.newCombo || setComboIndex)
        {
            combo = 1;
            comboIndex = ((comboIndex + 1) + hitObject.comboSkip) % this.Colors.length;
            setComboIndex = 0;
        }
        hitObject.combo = combo++;
        hitObject.color = (this.colorChange) ? this.Colors[i % this.Colors.length] : this.Colors[comboIndex];
    }


    // calculate stacks
    // https://gist.github.com/peppy/1167470
    for (var i = this.HitObjects.length - 1; i > 0; i--)
    {
        var hitObject = this.HitObjects[i];
        if (hitObject.stack != 0 || hitObject instanceof Spinner)
        {
            continue;
        }

        for (var n = i - 1; n >= 0; n--)
        {
            var hitObjectN = this.HitObjects[n];
            if (hitObjectN instanceof Spinner)
            {
                continue;
            }

            if (hitObject.time - hitObjectN.endTime > this.approachTime * this.StackLeniency)
            {
                break;
            }

            if (hitObject.position.distanceTo(hitObjectN.endPosition) < Standard.STACK_LENIENCE)
            {
                if (hitObjectN instanceof Slider)
                {
                    var offset = hitObject.stack - hitObjectN.stack + 1;
                    for (var j = n + 1; j <= i; j++)
                    {
                        var hitObjectJ = this.HitObjects[j];
                        if (hitObjectJ.position.distanceTo(hitObjectN.endPosition) < Standard.STACK_LENIENCE)
                        {
                            hitObjectJ.stack -= offset;
                        }
                    }
                    break;
                }

                hitObjectN.stack = hitObject.stack + 1;
                hitObject = hitObjectN;
            }
        }
    }

    this.circleRadius = this.circleDiameter / 2;
    this.circleBorder = this.circleRadius / 8;
    this.shadowBlur = this.circleRadius / 15;
}
Standard.prototype = Object.create(Beatmap.prototype, {
    approachTime: {
        get: function()
        {
            return this.ApproachRate < 5
                ? 1800 - this.ApproachRate * 120
                : 1200 - (this.ApproachRate - 5) * 150;
        }
    },
    // https://github.com/itdelatrisu/opsu/commit/8892973d98e04ebaa6656fe2a23749e61a122705
    circleDiameter: {
        get: function()
        {
            return 108.848 - this.CircleSize * 8.9646;
        }
    },
    stackOffset: {
        get: function()
        {
            return this.circleDiameter / 20;
        }
    }
});
Standard.prototype.constructor = Standard;
Standard.prototype.hitObjectTypes = {};
Standard.ID = 0;
Beatmap.modes[Standard.ID] = Standard;
Standard.DEFAULT_COLORS = [
    'rgb(0,202,0)',
    'rgb(18,124,255)',
    'rgb(242,24,57)',
    'rgb(255,255,0)'
];
Standard.STACK_LENIENCE = 3;
Standard.prototype.update = function(ctx)
{
    ctx.shadowColor = '#666';
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    try
    {
        // this code will fail in Firefox(<~ 44)
        // https://bugzilla.mozilla.org/show_bug.cgi?id=941146
        ctx.font = this.circleRadius + 'px "Comic Sans MS", cursive, sans-serif';
    }
    catch (e) {}
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.translate((Beatmap.WIDTH - Beatmap.MAX_X) / 2, (Beatmap.HEIGHT - Beatmap.MAX_Y) / 2);
};
Standard.prototype.draw = function(time, ctx)
{
    if (typeof this.tmp.first == 'undefined')
    {
        this.tmp.first = 0;
        this.tmp.last = -1;
    }

    while (this.tmp.first < this.HitObjects.length)
    {
        var hitObject = this.HitObjects[this.tmp.first];
        if (time <= hitObject.endTime + hitObject.__proto__.constructor.FADE_OUT_TIME)
        {
            break;
        }
        this.tmp.first++;
    }
    while (this.tmp.last + 1 < this.HitObjects.length &&
        time >= this.HitObjects[this.tmp.last + 1].time - this.approachTime)
    {
        this.tmp.last++;
    }
    for (var i = this.tmp.last; i >= this.tmp.first; i--)
    {
        var hitObject = this.HitObjects[i];
        if (time > hitObject.endTime + hitObject.__proto__.constructor.FADE_OUT_TIME)
        {
            continue;
        }
        hitObject.draw(time, ctx);
    }
};
