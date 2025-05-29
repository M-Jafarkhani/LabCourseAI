import Rhino.Geometry as rg
import Rhino
import os

def breps_to_meshes(breps, mesh_params=None):
    meshes = []
    if mesh_params is None:
        mesh_params = rg.MeshingParameters.Default
    for brep in breps:
        if brep is None:
            continue
        mesh_list = rg.Mesh.CreateFromBrep(brep, mesh_params)
        if mesh_list:
            for m in mesh_list:
                m.Faces.ConvertQuadsToTriangles()
                meshes.append(m)
    return meshes

def write_mesh_to_stl(mesh, path):
    """Write a single Rhino mesh as ASCII STL."""
    with open(path, "w") as f:
        f.write("solid ghmesh\n")
        for i in range(mesh.Faces.Count):
            face = mesh.Faces[i]
            if face.IsTriangle:
                idx = [face.A, face.B, face.C]
            elif face.IsQuad:
                idx = [face.A, face.B, face.C, face.D]
            else:
                continue  # should not occur
            pts = [mesh.Vertices[j] for j in idx]
            if len(pts) == 3:
                normal = mesh.Normals[face.A] if mesh.Normals.Count else rg.Vector3d(0,0,1)
                f.write("  facet normal {} {} {}\n".format(normal.X, normal.Y, normal.Z))
                f.write("    outer loop\n")
                for pt in pts:
                    f.write("      vertex {} {} {}\n".format(pt.X, pt.Y, pt.Z))
                f.write("    endloop\n")
                f.write("  endfacet\n")
            elif len(pts) == 4:
                # Write as two triangles
                for tri in [(0,1,2),(0,2,3)]:
                    normal = mesh.Normals[face.A] if mesh.Normals.Count else rg.Vector3d(0,0,1)
                    f.write("  facet normal {} {} {}\n".format(normal.X, normal.Y, normal.Z))
                    f.write("    outer loop\n")
                    for idx_tri in tri:
                        pt = pts[idx_tri]
                        f.write("      vertex {} {} {}\n".format(pt.X, pt.Y, pt.Z))
                    f.write("    endloop\n")
                    f.write("  endfacet\n")
        f.write("endsolid ghmesh\n")

def get_next_free_filename(basepath, basefilename):
    """
    Find the next available buildingN filename (returns the full path without extension).
    """
    i = 1
    while True:
        filename = f"{basefilename}{i}"
        paths = [os.path.join(basepath, filename + ext) for ext in [".ttl", ".json", ".stl"]]
        if not any(os.path.exists(p) for p in paths):
            return os.path.join(basepath, filename)
        i += 1

# --- Inputs: ttl_text, json_text, building, basepath (e.g., r"C:\Users\You\Desktop") ---

if export:
    basefilename = "building"
    save_path = get_next_free_filename(path, basefilename)

    # Write TTL and JSON
    with open(save_path + ".ttl", "w", encoding="utf-8") as f:
        f.write(ttl)
    with open(save_path + ".json", "w", encoding="utf-8") as f:
        f.write(json)

    # Extract geometry from building
    slabs = []
    if hasattr(building, "floor_slab") and building.floor_slab:
        slabs.append(building.floor_slab)
    if hasattr(building, "slabs") and building.slabs:
        slabs += [s for s in building.slabs if s]
    if hasattr(building, "roof_slab") and building.roof_slab:
        slabs.append(building.roof_slab)
    walls = []
    if hasattr(building, "walls"):
        for storey_walls in building.walls:
            walls += [w for w in storey_walls if w]
    columns = []
    if hasattr(building, "columns"):
        for storey_columns in building.columns:
            columns += [c for c in storey_columns if c]

    all_breps = slabs + walls + columns
    all_meshes = breps_to_meshes(all_breps)

    # Export as STL
    combined = rg.Mesh()
    for m in all_meshes:
        combined.Append(m)
    if not combined.IsValid or combined.Faces.Count == 0:
        raise Exception("Combined mesh is not valid or empty.")

    # Write the STL file
    write_mesh_to_stl(combined, save_path + ".stl")

    # Optional: Output the actual filenames as Grasshopper output params
    ttl_file = save_path + ".ttl"
    json_file = save_path + ".json"
    stl_file = save_path + ".stl"
