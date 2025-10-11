function Catch(osu) {
    Beatmap.call(this, osu);

    let savedDefaultColor = window.localStorage.getItem("DefaultColor");
    this.useDefaultColor = (savedDefaultColor) ? parseInt(savedDefaultColor) : 0;

    let savedColorChange = window.localStorage.getItem("ColorChange");
    this.colorChange = (savedColorChange) ? parseInt(savedColorChange) : 0;

    if (this.Colors.length && !this.useDefaultColor) {
        this.Colors.push(this.Colors.shift());
    }
    else {
        this.Colors = Catch.DEFAULT_COLORS;
    }

    this.circleRadius = this.circleDiameter / 2 - 4;
    this.smallRadius = this.circleRadius / 2;
    this.tinyRadius = this.smallRadius / 2;
    this.bananaRadius = this.circleRadius * 0.8;

    this.CATCHER_HEIGHT = Beatmap.HEIGHT / 8;
    this.FALLOUT_TIME = (this.CATCHER_HEIGHT / Beatmap.HEIGHT) * this.approachTime;

    var combo = 1,
        comboIndex = -1,
        setComboIndex = 1;
    for (var i = 0; i < this.HitObjects.length; i++) {
        let hitObject = this.HitObjects[i];
        if (hitObject instanceof BananaShower) {
            setComboIndex = 1;
        }
        else if (hitObject.newCombo || setComboIndex) {
            combo = 1;
            comboIndex = ((comboIndex + 1) + hitObject.comboSkip) % this.Colors.length;
            setComboIndex = 0;
        }
        hitObject.combo = combo++;
        hitObject.color = (this.colorChange) ? this.Colors[i % this.Colors.length] : this.Colors[comboIndex];

        if (hitObject instanceof JuiceStream || hitObject instanceof BananaShower) {
            hitObject.buildNested();
        }
    }

    this.CATCHER_BASE_SIZE = 106.75;
    this.ALLOWED_CATCH_RANGE = 0.8;
    this.HYPER_DASH_TRANSITION_DURATION = 180;
    this.calculateScale = 1.0 - 0.7 * (this.CircleSize - 5) / 5;
    this.catchWidth = this.CATCHER_BASE_SIZE * Math.abs(this.calculateScale) * this.ALLOWED_CATCH_RANGE;
    this.halfCatcherWidth = this.catchWidth / 2;
    this.halfCatcherWidth /= this.ALLOWED_CATCH_RANGE;
    this.BASE_DASH_SPEED = 1;
    this.BASE_WALK_SPEED = 0.5;

    // sliders & spins xoffset
    this.RNG_SEED = 1337;
    var rng = new LegacyRandom(this.RNG_SEED);

    for (var i = 0; i < this.HitObjects.length; i++) {
        let hitObject = this.HitObjects[i];
        // console.log(hitObject.nested)
        if (hitObject instanceof BananaShower) {
            hitObject.nested.forEach(banana => {
                banana.x += (rng.NextDouble() * Beatmap.MAX_X);
                rng.Next(); // osu!stable retrieved a random banana type
                rng.Next(); // osu!stable retrieved a random banana rotation
                rng.Next(); // osu!stable retrieved a random banana colour
            });
        }
        else if (hitObject instanceof JuiceStream) {
            hitObject.nested.forEach(item => {
                if (item.type === "TinyDroplet") item.x += Math.clamp(rng.Next(-20, 20), -item.x, Beatmap.MAX_X - item.x);
                else if (item.type === "Droplet") rng.Next(); // osu!stable retrieved a random droplet rotation
            });
        }
    }

    // catch objects
    this.palpableObjects = [];
    this.fullCatchObjects = [];
    for (var i = 0; i < this.HitObjects.length; i++) {
        let hitObject = this.HitObjects[i];
        if (hitObject instanceof Fruit) {
            let pch = new PalpableCatchHitObject({
                type: "Fruit",
                time: hitObject.time,
                x: hitObject.position.x,
                color: hitObject.color,
                radius: this.circleRadius,
            }, this);

            this.palpableObjects.push(pch);
            this.fullCatchObjects.push(pch);
        }
        else if (hitObject instanceof BananaShower) {
            hitObject.nested.forEach(banana => {
                this.fullCatchObjects.push(banana);
            });
        }
        else if (hitObject instanceof JuiceStream) {
            hitObject.nested.forEach(item => {
                this.fullCatchObjects.push(item);
                if (item.type != "TinyDroplet") this.palpableObjects.push(item);
            });
        }
    }

    this.palpableObjects.sort((a, b) => a.time - b.time);
    this.fullCatchObjects.sort((a, b) => a.time - b.time);

    // hyperdash
    let lastDirection = 0;
    let lastExcess = this.halfCatcherWidth;

    for (let i = 0; i < this.palpableObjects.length - 1; i++) {
        var currentObject = this.palpableObjects[i];
        var nextObject = this.palpableObjects[i + 1];

        currentObject.hyperDash = false;

        let thisDirection = nextObject.x > currentObject.x ? 1 : -1;
        let timeToNext = nextObject.time - currentObject.time - 1000 / 60 / 4; // 1/4th of a frame of grace time, taken from osu-stable
        let distanceToNext = Math.abs(nextObject.x - currentObject.x) - (lastDirection == thisDirection ? lastExcess : this.halfCatcherWidth);
        let distanceToHyper = timeToNext * this.BASE_DASH_SPEED - distanceToNext;

        if (distanceToHyper < 0) {
            currentObject.hyperDash = true;
            lastExcess = this.halfCatcherWidth;
        }
        else {
            lastExcess = Math.clamp(distanceToHyper, 0, this.halfCatcherWidth);
        }

        lastDirection = thisDirection;
    }

}
Catch.prototype = Object.create(Beatmap.prototype, {
    approachTime: { // droptime
        get: function () {
            return this.ApproachRate < 5
                ? 1800 - this.ApproachRate * 120
                : 1200 - (this.ApproachRate - 5) * 150;
        }
    },
    // https://github.com/itdelatrisu/opsu/commit/8892973d98e04ebaa6656fe2a23749e61a122705
    circleDiameter: {
        get: function () {
            return 108.848 - this.CircleSize * 8.9646;
        }
    }
});
Catch.prototype.constructor = Catch;
Catch.prototype.hitObjectTypes = {};
Catch.ID = 2;
Beatmap.modes[Catch.ID] = Catch;
Catch.DEFAULT_COLORS = [
    'rgb(255,210,128)',
    'rgb(128,255,128)',
    'rgb(128,191,255)',
    'rgb(191,128,255)'
];
Catch.prototype.update = function (ctx) {
    ctx.translate((Beatmap.WIDTH - Beatmap.MAX_X) / 2, (Beatmap.HEIGHT - Beatmap.MAX_Y) / 2);
};
Catch.prototype.draw = function (time, ctx) {
    if (typeof this.tmp.first == 'undefined') {
        this.tmp.first = 0;
        this.tmp.last = -1;
    }

    while (this.tmp.first < this.fullCatchObjects.length) {
        var catchHitObject = this.fullCatchObjects[this.tmp.first];
        if (time <= catchHitObject.time + this.FALLOUT_TIME) {
            break;
        }
        this.tmp.first++;
    }
    while (this.tmp.last + 1 < this.fullCatchObjects.length &&
        time >= this.fullCatchObjects[this.tmp.last + 1].time - this.approachTime * 1.1) {
        this.tmp.last++;
    }
    for (var i = this.tmp.last; i >= this.tmp.first; i--) {
        var catchHitObject = this.fullCatchObjects[i];
        if (time > catchHitObject.time + this.FALLOUT_TIME) {
            continue;
        }
        catchHitObject.draw(time, ctx);
    }
};
Catch.prototype.processBG = function (ctx) {
    let xoffset = (Beatmap.WIDTH - Beatmap.MAX_X) / 2;
    let yoffset = (Beatmap.HEIGHT - Beatmap.MAX_Y) / 2;
    // line
    ctx.beginPath();
    ctx.moveTo(-xoffset, Beatmap.HEIGHT - this.CATCHER_HEIGHT - yoffset);
    ctx.lineTo(Beatmap.WIDTH - xoffset, Beatmap.HEIGHT - this.CATCHER_HEIGHT - yoffset);
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 1;
    ctx.stroke();
    // plate
    let plateHeight = 20;
    ctx.beginPath();
    ctx.rect(Beatmap.WIDTH / 2 - this.catchWidth / 2 - xoffset, Beatmap.HEIGHT - this.CATCHER_HEIGHT - plateHeight / 2 - yoffset, this.catchWidth, plateHeight);
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 8;
    ctx.stroke();
    ctx.fillStyle = '#fff';
    ctx.fill();
};
