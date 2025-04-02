## self.env.stepレスポンス例

### Codeデータを送信した場合のレスポンス例
```
[
  [
    'onChat', 
    {
      'onChat': 'Cannot plant oak sapling at (-1.2999999999999998, 72, -26.50000008719197), not a valid block.',
      'voxels': ['dirt', 'grass_block', 'grass', 'stone', 'coal_ore', 'diamond_block', 'pearlescent_froglight', 'redstone_torch'],
      'status': {
        'health': 20,
        'food': 20,
        'saturation': 1,
        'position': {'x': -2.3, 'y': 72, 'z': -26.50000008719197},
        'velocity': {'x': 0, 'y': -0.0784000015258789, 'z': 0},
        'yaw': 4.712389513016908,
        'pitch': 0.0010692924671804604,
        'onGround': True,
        'equipment': [None, None, None, None, 'oak_sapling', None],
        'name': 'bot',
        'timeSinceOnGround': 0,
        'isInWater': False,
        'isInLava': False,
        'isCollidedHorizontally': False,
        'isCollidedVertically': True,
        'biome': 'forest',
        'entities': {},
        'timeOfDay': 'day',
        'inventoryUsed': 4,
        'elapsedTime': 1
      },
      'inventory': {'oak_sapling': 10, 'oak_log': 13, 'birch_log': 9, 'stick': 1},
      'nearbyChests': {},
      'blockRecords': ['dirt', 'grass_block', 'grass', 'stone', 'coal_ore', 'diamond_block', 'pearlescent_froglight', 'redstone_torch']
    }
  ],
  [
    'onChat', 
    {
      'onChat': 'Cannot plant oak sapling at (-0.2999999999999998, 72, -26.50000008719197), not a valid block.',
      'voxels': ['dirt', 'grass_block', 'grass', 'stone', 'coal_ore', 'diamond_block', 'pearlescent_froglight', 'redstone_torch'],
      'status': {
        'health': 20,
        'food': 20,
        'saturation': 1,
        'position': {'x': -2.3, 'y': 72, 'z': -26.50000008719197},
        'velocity': {'x': 0, 'y': -0.0784000015258789, 'z': 0},
        'yaw': 4.712389513016908,
        'pitch': 0.0010692924671804604,
        'onGround': True,
        'equipment': [None, None, None, None, 'oak_sapling', None],
        'name': 'bot',
        'timeSinceOnGround': 0,
        'isInWater': False,
        'isInLava': False,
        'isCollidedHorizontally': False,
        'isCollidedVertically': True,
        'biome': 'forest',
        'entities': {},
        'timeOfDay': 'day',
        'inventoryUsed': 4,
        'elapsedTime': 1
      },
      'inventory': {'oak_sapling': 10, 'oak_log': 13, 'birch_log': 9, 'stick': 1},
      'nearbyChests': {},
      'blockRecords': ['dirt', 'grass_block', 'grass', 'stone', 'coal_ore', 'diamond_block', 'pearlescent_froglight', 'redstone_torch']
    }
  ],
  [
    'onChat', 
    {
      'onChat': 'Cannot plant oak sapling at (0.7000000000000002, 72, -26.50000008719197), not a valid block.',
      'voxels': ['dirt', 'grass_block', 'grass', 'stone', 'coal_ore', 'diamond_block', 'pearlescent_froglight', 'redstone_torch'],
      'status': {
        'health': 20,
        'food': 20,
        'saturation': 1,
        'position': {'x': -2.3, 'y': 72, 'z': -26.50000008719197},
        'velocity': {'x': 0, 'y': -0.0784000015258789, 'z': 0},
        'yaw': 4.712389513016908,
        'pitch': 0.0010692924671804604,
        'onGround': True,
        'equipment': [None, None, None, None, 'oak_sapling', None],
        'name': 'bot',
        'timeSinceOnGround': 0,
        'isInWater': False,
        'isInLava': False,
        'isCollidedHorizontally': False,
        'isCollidedVertically': True,
        'biome': 'forest',
        'entities': {},
        'timeOfDay': 'day',
        'inventoryUsed': 4,
        'elapsedTime': 1
      },
      'inventory': {'oak_sapling': 10, 'oak_log': 13, 'birch_log': 9, 'stick': 1},
      'nearbyChests': {},
      'blockRecords': ['dirt', 'grass_block', 'grass', 'stone', 'coal_ore', 'diamond_block', 'pearlescent_froglight', 'redstone_torch']
    }
  ],
  [
    'observe', 
    {
      'voxels': ['dirt', 'grass_block', 'grass', 'stone', 'coal_ore', 'diamond_block', 'pearlescent_froglight', 'redstone_torch'],
      'status': {
        'health': 20,
        'food': 20,
        'saturation': 1,
        'position': {'x': -2.3, 'y': 72, 'z': -26.50000008719197},
        'velocity': {'x': 0, 'y': -0.0784000015258789, 'z': 0},
        'yaw': 4.712389513016908,
        'pitch': 0.0010692924671804604,
        'onGround': True,
        'equipment': [None, None, None, None, 'oak_sapling', None],
        'name': 'bot',
        'timeSinceOnGround': 0,
        'isInWater': False,
        'isInLava': False,
        'isCollidedHorizontally': False,
        'isCollidedVertically': True,
        'biome': 'forest',
        'entities': {},
        'timeOfDay': 'day',
        'inventoryUsed': 4,
        'elapsedTime': 52
      },
      'inventory': {'oak_sapling': 10, 'oak_log': 13, 'birch_log': 9, 'stick': 1},
      'nearbyChests': {},
      'blockRecords': ['dirt', 'grass_block', 'grass', 'stone', 'coal_ore', 'diamond_block', 'pearlescent_froglight', 'redstone_torch']
    }
  ]
]
```

### ""にて送信した場合
```
[
 [
   "observe",
   {
     "voxels": [
       "dirt",
       "grass_block",
       "grass",
       "stone",
       "coal_ore",
       "birch_leaves",
       "redstone_torch",
       "campfire",
       "oak_log",
       "birch_log"
     ],
     "status": {
       "health": 20,
       "food": 20,
       "saturation": 1,
       "oxygen": 20,
       "position": {
         "x": -2.3,
         "y": 72,
         "z": -26.50000008719197
       },
       "velocity": {
         "x": 0,
         "y": -0.0784000015258789,
         "z": 0
       },
       "yaw": 4.712389513016908,
       "pitch": 0.0010692924671804604,
       "onGround": true,
       "equipment": [
         null,
         null,
         null,
         null,
         "oak_sapling",
         null
       ],
       "name": "bot",
       "timeSinceOnGround": 0,
       "isInWater": false,
       "isInLava": false,
       "isCollidedHorizontally": false,
       "isCollidedVertically": true,
       "biome": "forest",
       "entities": {},
       "timeOfDay": "midnight",
       "inventoryUsed": 4,
       "elapsedTime": 51
     },
     "inventory": {
       "oak_sapling": 3,
       "oak_log": 13,
       "birch_log": 9,
       "stick": 1
     },
     "nearbyChests": {},
     "blockRecords": []
   }
 ]
]
```

## self.langflow_chat.run_flowのレスポンス例

```