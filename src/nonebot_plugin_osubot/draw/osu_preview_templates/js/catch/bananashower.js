function BananaShower(data, beatmap) {
    Spinner.call(this, data, beatmap);

    this.endTime = data[5] | 0;
    this.duration = this.endTime - this.time;

    this.nested = [];
}
BananaShower.prototype = Object.create(Spinner.prototype);
BananaShower.prototype.constructor = BananaShower;
BananaShower.ID = 8;
Catch.prototype.hitObjectTypes[BananaShower.ID] = BananaShower;
BananaShower.prototype.buildNested = function() {
    this.nested = [];
    let spacing = this.duration;
    while (spacing > 100) spacing /= 2;
    if (spacing <= 0) return;
    let time = this.time;
    let i = 0;
    while (time <= this.endTime) {
        this.nested.push(new PalpableCatchHitObject({
            type: "Banana",
            time,
            x: 0,
            color: 'rgb(255,240,0)',
            radius: this.beatmap.bananaRadius,
        }, this.beatmap));

        time += spacing;
        i++;
    }
    return this;
};
