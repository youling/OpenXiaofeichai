"""Synthetic transport probe, not a Xiaofeichai candidate. Run with Blender --background."""
import bpy, math, json, struct, hashlib, sys, argparse
from pathlib import Path

args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
p = argparse.ArgumentParser()
p.add_argument('--out', default=str(Path(__file__).resolve().parent))
out = Path(p.parse_args(args).out)
out.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.frame_start, scene.frame_end = 1, 25
scene.render.fps = 24
vertices = [(x, y, z) for z in (0., 1., 2.) for x, y in ((-.2, -.2), (.2, -.2), (.2, .2), (-.2, .2))]
faces = [(0, 3, 2, 1), (8, 9, 10, 11)]
for ring in (0, 1):
    for side in range(4):
        a = ring * 4 + side
        b = ring * 4 + (side + 1) % 4
        faces.append((a, b, b + 4, a + 4))
mesh = bpy.data.meshes.new('ProbeMesh')
mesh.from_pydata(vertices, [], faces)
mesh.update()
obj = bpy.data.objects.new('ProbeActor', mesh)
scene.collection.objects.link(obj)
mat = bpy.data.materials.new('ProbeMat')
mat.diffuse_color = (.2, .55, .8, 1)
mat.use_nodes = True
mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = (.2, .55, .8, 1)
obj.data.materials.append(mat)
obj.shape_key_add(name='Basis')
bulge = obj.shape_key_add(name='Bulge')
for i in range(4, 8):
    bulge.data[i].co.x *= 1.8
    bulge.data[i].co.y *= 1.8
for frame, value in ((1, 0.), (13, 1.), (25, 0.)):
    bulge.value = value
    bulge.keyframe_insert('value', frame=frame)
obj.data.shape_keys.animation_data.action.name = 'ProbeMorph'
arm_data = bpy.data.armatures.new('ProbeRigData')
arm = bpy.data.objects.new('ProbeRig', arm_data)
scene.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
arm.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
base = arm_data.edit_bones.new('Base')
base.head, base.tail = (0, 0, 0), (0, 0, 1)
tip = arm_data.edit_bones.new('Tip')
tip.head, tip.tail = (0, 0, 1), (0, 0, 2)
tip.parent = base
tip.use_connect = True
bpy.ops.object.mode_set(mode='OBJECT')
base_group = obj.vertex_groups.new(name='Base')
tip_group = obj.vertex_groups.new(name='Tip')
base_group.add(list(range(4)), 1., 'REPLACE')
base_group.add(list(range(4, 8)), .5, 'REPLACE')
tip_group.add(list(range(4, 8)), .5, 'REPLACE')
tip_group.add(list(range(8, 12)), 1., 'REPLACE')
modifier = obj.modifiers.new(name='ProbeSkin', type='ARMATURE')
modifier.object = arm
obj.parent = arm
tip_pose = arm.pose.bones['Tip']
tip_pose.rotation_mode = 'XYZ'
for frame, angle in ((1, 0.), (13, .65), (25, 0.)):
    tip_pose.rotation_euler.x = angle
    tip_pose.keyframe_insert('rotation_euler', frame=frame)
arm.animation_data.action.name = 'ProbeBones'
scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'sample.blend'))
bpy.ops.export_scene.gltf(filepath=str(out/'sample.glb'), export_format='GLB',
    export_animations=True, export_animation_mode='SCENE', export_skins=True,
    export_morph=True, export_force_sampling=True, export_frame_range=True,
    export_anim_scene_split_object=False)
raw = (out/'sample.glb').read_bytes()
magic, version, size = struct.unpack_from('<4sII', raw)
assert magic == b'glTF' and size == len(raw)
length, kind = struct.unpack_from('<II', raw, 12)
doc = json.loads(raw[20:20+length])
paths = [c['target']['path'] for a in doc.get('animations', []) for c in a['channels']]
primitives = [p for m in doc['meshes'] for p in m['primitives']]
assert len(doc.get('skins', [])) == 1
assert len(doc['skins'][0]['joints']) == 2
assert all('JOINTS_0' in p['attributes'] and 'WEIGHTS_0' in p['attributes'] for p in primitives)
assert all(len(p.get('targets', [])) == 1 for p in primitives)
assert 'rotation' in paths and 'weights' in paths
export = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
    'skins': len(doc['skins']), 'joints': len(doc['skins'][0]['joints']),
    'primitive_attributes': [list(p['attributes']) for p in primitives],
    'morph_targets_per_primitive': [len(p['targets']) for p in primitives],
    'animations': len(doc.get('animations', [])), 'channel_paths': paths,
    'animation_names': [a.get('name') for a in doc.get('animations', [])]}
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(out/'sample.glb'))
re_meshes = [o for o in bpy.data.objects if o.type == 'MESH']
re_arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
assert len(re_arms) == 1 and len(re_arms[0].data.bones) == 2
assert any(o.data.shape_keys and len(o.data.shape_keys.key_blocks) == 2 for o in re_meshes)
actor = next(o for o in re_meshes if o.data.shape_keys and len(o.data.shape_keys.key_blocks) == 2)
snapshots = []
for frame in (1, 13, 25):
    bpy.context.scene.frame_set(frame)
    graph = bpy.context.evaluated_depsgraph_get()
    ev = actor.evaluated_get(graph)
    positions = [tuple(ev.matrix_world @ v.co) for v in ev.data.vertices]
    snapshots.append({'frame': frame, 'position_sum': [sum(p[i] for p in positions) for i in range(3)],
        'position_sha256': hashlib.sha256(json.dumps(positions).encode()).hexdigest(),
        'shape_value': actor.data.shape_keys.key_blocks[1].value})
print('REIMPORT_SNAPSHOTS', snapshots)
assert snapshots[0]['position_sha256'] != snapshots[1]['position_sha256']
assert abs(snapshots[1]['shape_value']-1.) < 1e-5
assert abs(snapshots[0]['shape_value']) < 1e-5
result = {'scope': 'Synthetic two-bone and one-morph transport probe; not character or browser acceptance',
    'blender_version': bpy.app.version_string, 'export': export,
    'reimport': {'armatures': len(re_arms), 'bones': len(re_arms[0].data.bones),
        'mesh_shape_keys': [o.data.shape_keys.key_blocks.keys() if o.data.shape_keys else [] for o in re_meshes],
        'snapshots': snapshots}, 'status': 'PASS'}
(out/'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
