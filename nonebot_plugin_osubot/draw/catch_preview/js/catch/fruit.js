function Fruit(data, beatmap)
{
    HitObject.call(this, data, beatmap);
}
Fruit.prototype = Object.create(HitObject.prototype, {
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
Fruit.prototype.constructor = Fruit;
Fruit.ID = 1;
Catch.prototype.hitObjectTypes[Fruit.ID] = Fruit;