#!/usr/bin/env python
# encoding: utf-8

import sys, os, re
from collections import defaultdict
from PASA_SALRAA_Globals import SPACER
from Splice_graph import Splice_graph
from GenomeFeature import Exon


# Namespace: Simple_path_utils
# includes basic functions for evaluating relationships between simple paths in the graph.



## Scenarios:
#
## Scenario 1
## path_A  ==============
## path_B        ===============  (idx_B == 0)
## or
#
## Scenario 2
## path_A        ================= (idx_A == 0)
## path_B  ==============
## or
#
## Scenarion 3
## path_A  ======================= (idx_B == 0)
## path_B         =======
## or
#
#  Scenario 4
## path_A         =======
## path_B  ======================= (idx_A == 0)
## or
#
# Scenario 5
## path_A       ==========     or   ============   or =====        (either are idx 0)
## path_B       ==========          ====              ===========



def path_A_contains_path_B(simple_path_A, simple_path_B):

    if len(simple_path_B) > len(simple_path_A):
        return False

    if simple_path_B[0] not in simple_path_A:
        return False
    
    idx_A = simple_path_A.index(simple_path_B[0])
    if idx_A < 0:
        return False

    if idx_A + len(simple_path_B) > len(simple_path_A):
        return False

    idx_B = 0
    while idx_B < len(simple_path_B):
        idx_B += 1
        idx_A += 1
        if (idx_B < len(simple_path_B) and
            idx_A < len(simple_path_A) and
            simple_path_A[idx_A] != simple_path_B[idx_B]):
            return False

    return True


def are_overlapping_and_compatible_NO_gaps_in_overlap(simple_path_A, simple_path_B):
    
    ## find first non-spacer match between two paths.  Ensure remaining parts of paths are identical
    for idx_A in range(0, len(simple_path_A)):
        A_node_id = simple_path_A[idx_A]
        if A_node_id == SPACER:
            continue
        if A_node_id in simple_path_B:
            idx_B = simple_path_B.index(A_node_id)

            ## one of the indexes needs to start at zero or there'll be some unmatched upstream nodes.
            if (idx_B != 0 and idx_A != 0):
                return False

            # ensure remainder of paths overlap, no gaps allowed.
            idx_A += 1
            idx_B += 1
            while (idx_A < len(simple_path_A) and idx_B < len(simple_path_B)):
                if simple_path_A[idx_A] == SPACER or simple_path_A[idx_A] != simple_path_B[idx_B]:
                    return False
                idx_A += 1
                idx_B += 1
                
            # if made it here, the remainder of the paths are gap-free and identical
            return True

    return False # no matching index between paths



def merge_simple_paths(simple_path_A, simple_path_B):
    
    if not are_overlapping_and_compatible_NO_gaps_in_overlap(simple_path_A, simple_path_B):
        raise RuntimeException("cannot merge paths that are not compatible in overlapping region")


    ## find first non-spacer match between two paths, then merge.
    for idx_A in range(0, len(simple_path_A)):
        A_node_id = simple_path_A[idx_A]
        if A_node_id == SPACER:
            continue
        if A_node_id in simple_path_B:
            idx_B = simple_path_B.index(A_node_id)

            merged_path = None
            if idx_A == 0: # scenarios 2,4,5
                if idx_B > 0: # scenario 2 or 4
                    # begin path with B prefix
                    merged_path = simple_path_B
                    # if A extends past B, need to include that.
                    #  path A:        0 1 2 3 4 5 6
                    #  path B:    0 1 2 3 4 5 6
                    extension_idx_A = len(simple_path_B) - idx_B
                    if extension_idx_A < len(simple_path_A):
                        merged_path.extend(simple_path_A[extension_idx_A: ])
                    return merged_path
                else: #scenario 5, return longer path
                    if len(simple_path_A) >= len(simple_path_B):
                        return simple_path_A
                    else:
                        return simple_path_B
            
            else:
                # idx_A != 0, so idx_B must be == 0
                assert(idx_B == 0)
                # scenarios 1,3
                # begin path with A prefix
                merged_path = simple_path_A
                # if A extends past B, need to include that.
                #  path A:   0 1 2 3 4 5 6
                #  path B:         0 1 2 3 4 5 6
                extension_idx_B = len(simple_path_A) - idx_A
                if extension_idx_B < len(simple_path_B):
                    merged_path.extend(simple_path_B[extension_idx_B: ])
                return merged_path
            
    raise RuntimeException("Error, could not merge simple paths {} and {} ... bug... ".format(simple_path_A, simple_path_B))



def merge_adjacent_segments(segment_list):

    segment_list = sorted(segment_list, key=lambda x: x[0])
    
    ret_segments = list()
    ret_segments.append(list(segment_list.pop(0)))

    while len(segment_list) > 0:
        next_seg = list(segment_list.pop(0))

        prev_seg = ret_segments[-1]
        if next_seg[0] == prev_seg[1] + 1:
            # merge them
            assert(next_seg[1] > prev_seg[1])
            prev_seg[1] = next_seg[1]
        elif prev_seg[1] == next_seg[1] and prev_seg[0] <= next_seg[0]:
            # identical or contained feature - skip it.
            pass
        elif next_seg[0] > prev_seg[1]:
            ret_segments.append(next_seg)
        else:
            raise RuntimeError("Error, not sure hwo to merge adjacent segments: {} and {}".format(prev_seg, next_seg))

    
    return ret_segments




def _convert_path_to_nodes_with_coords_list(sg:Splice_graph, simple_path:list) -> list:

    node_ids_with_coords_list = list()
    found_spacer = False
    for i, node_id in enumerate(simple_path):
        if node_id != SPACER:
            lend, rend = sg.get_node_obj_via_id(node_id).get_coords()
            node_id_w_coords = [node_id, lend, rend]
            node_ids_with_coords = node_id_w_coords
            node_ids_with_coords_list.append(node_ids_with_coords)
        else:
            found_spacer = True
            node_ids_with_coords_list.append([SPACER, -1, -1])


    if found_spacer:
        # adjust spacer coordinates to neighboring bounds of nodes.
        for i, node_info_list in enumerate(node_ids_with_coords_list):
            if node_info_list[0] == SPACER:
                node_info_list[1] = node_ids_with_coords_list[i-1][2] + 1
                node_info_list[2] = node_ids_with_coords_list[i+1][1] -1

    return node_ids_with_coords_list



def _split_spacers_with_coords(simple_path_w_coords:list) -> list:

    adj_list = list()

    for node_coordset in simple_path_w_coords:
        node_id, lend, rend = node_coordset
        if node_id == SPACER:
            adj_list.append([SPACER, lend, lend])
            adj_list.append([SPACER, rend, rend])
        else:
            adj_list.append(node_coordset)

    return adj_list




def merge_simple_paths_containing_spacers(sg:Splice_graph, simple_path_A:list, simple_path_B:list) -> list:

    """
    Remove redundancies and adjust SPACER coordinates
    """

    
    A_list = _convert_path_to_nodes_with_coords_list(sg, simple_path_A)
    A_list = _split_spacers_with_coords(A_list)
    
    B_list = _convert_path_to_nodes_with_coords_list(sg, simple_path_B)
    B_list = _split_spacers_with_coords(B_list)

    
    merged_list = A_list + B_list
    merged_list = sorted(merged_list, key=lambda x: (x[1], x[2]) )

    adj_merged_list = list()
    adj_merged_list.append(merged_list.pop(0))
    
    for entry in merged_list:
        prev_entry = adj_merged_list[-1]
        prev_node_id, prev_lend, prev_rend = prev_entry

        curr_node_id, curr_lend, curr_rend = entry

        if prev_node_id == curr_node_id:
            if curr_node_id == SPACER:
                if curr_rend > prev_rend:
                    prev_entry[2] = curr_rend
            else:
                assert(prev_lend == curr_lend and prev_rend == curr_rend)

        else:
            adj_merged_list.append(entry)

    
    return adj_merged_list



###############
# unit tests ##
###############


def test_are_overlapping_and_compatible_NO_gaps_in_overlap():
    
    # Tests that should return True

    path_a = ["n0", "n1", "n2", "n3", "n4", "n5", "n6"]
    path_b =             ["n2", "n3", "n4", "n5", "n6", "n7", "n8"]
    test = are_overlapping_and_compatible_NO_gaps_in_overlap(path_a, path_b)
    print("path_a: {}\npath_b: {}\ncompatible_NO_gaps: {}".format(path_a, path_b, test))
    assert(test is True)


    path_a = ["n0", "n1", "n2", "n3", "n4", "n5", "n6"]
    path_b =             ["n2", "n3", "n4", "n5"]
    test = are_overlapping_and_compatible_NO_gaps_in_overlap(path_a, path_b)
    print("path_a: {}\npath_b: {}\ncompatible_NO_gaps: {}".format(path_a, path_b, test))
    assert(test is True)

    
    path_a =              ["n2", "n3", "n4", "n5"]
    path_b = ["n0", "n1", "n2", "n3", "n4", "n5", "n6"]
    test = are_overlapping_and_compatible_NO_gaps_in_overlap(path_a, path_b)
    print("path_a: {}\npath_b: {}\ncompatible_NO_gaps: {}".format(path_a, path_b, test))
    assert(test is True)


    path_a =             ["n2", "n3", "n4", "n5", "n6", "n7", "n8"]
    path_b = ["n0", "n1", "n2", "n3", "n4", "n5", "n6"]
    test = are_overlapping_and_compatible_NO_gaps_in_overlap(path_a, path_b)
    print("path_a: {}\npath_b: {}\ncompatible_NO_gaps: {}".format(path_a, path_b, test))
    assert(test is True)

    

    ################################
    # Tests that should return False

    path_a =             ["n2", "n10", "n4", "n5", "n6", "n7", "n8"]
    path_b = ["n0", "n1", "n2", "n3", "n4", "n5", "n6"]
    test = are_overlapping_and_compatible_NO_gaps_in_overlap(path_a, path_b)
    print("path_a: {}\npath_b: {}\ncompatible_NO_gaps: {}".format(path_a, path_b, test))
    assert(test is False)
    
        
    path_a =             ["n2", "X10", "n4", "n5", "n6", "n7", "n8"]
    path_b = ["n0", "n1", "n2", "n3", "n4", "n5", "n6"]
    test = are_overlapping_and_compatible_NO_gaps_in_overlap(path_a, path_b)
    print("path_a: {}\npath_b: {}\ncompatible_NO_gaps: {}".format(path_a, path_b, test))
    assert(test is False)

    
    path_a = ["n2", "n10"]
    path_b =               ["n3", "n4", "n5", "n6"]
    test = are_overlapping_and_compatible_NO_gaps_in_overlap(path_a, path_b)
    print("path_a: {}\npath_b: {}\ncompatible_NO_gaps: {}".format(path_a, path_b, test))
    assert(test is False)
    


def test_merge_simple_paths():
    
    ###################
    ## Test merging paths

    path_a = ["n1", "n2", "n3"]
    path_b =       ["n2", "n3", "n4", "n5"]
    merged_path = merge_simple_paths(path_a, path_b)
    print("path_a: {}\npath_b: {}\nmerged_path: {}".format(path_a, path_b, merged_path))
    assert(merged_path == ["n1", "n2", "n3", "n4", "n5"])



    path_a = ["n1", "n2", "n3"]
    path_b =       ["n2", "n3"]
    merged_path = merge_simple_paths(path_a, path_b)
    print("path_a: {}\npath_b: {}\nmerged_path: {}".format(path_a, path_b, merged_path))
    assert(merged_path == ["n1", "n2", "n3"])


    path_a =              ["n3", "n4", "n5"]
    path_b = ["n1", "n2", "n3"]
    merged_path = merge_simple_paths(path_a, path_b)
    print("path_a: {}\npath_b: {}\nmerged_path: {}".format(path_a, path_b, merged_path))
    assert(merged_path == ["n1", "n2", "n3", "n4", "n5"])


def test_path_A_contains_path_B():
    
    ####################
    ## Test containments
    path_a = ["n1", "n2", "n3"]
    path_b =       ["n2"]
    test = path_A_contains_path_B(path_a, path_b)
    print("path_a: {} contains path_b: {} = {}".format(path_a, path_b, test))
    assert(test is True)


    path_a = ["n1", "n2", "n3"]
    path_b = ["n1", "n2", "n3"]
    test = path_A_contains_path_B(path_a, path_b)
    print("path_a: {} contains path_b: {} = {}".format(path_a, path_b, test))
    assert(test is True)


    path_a = ["n1", "n2", "n3"]
    path_b = ["n1", "n2", "n3", "n4"]
    test = path_A_contains_path_B(path_a, path_b)
    print("path_a: {} contains path_b: {} = {}".format(path_a, path_b, test))
    assert(test is False)

    path_a = ["n1", "n2", "n3"]
    path_b = ["n0", "n1", "n2", "n3", "n4"]
    test = path_A_contains_path_B(path_a, path_b)
    print("path_a: {} contains path_b: {} = {}".format(path_a, path_b, test))
    assert(test is False)


    path_a = ["n1", "n2", "n3"]
    path_b = ["n3", "n4"]
    test = path_A_contains_path_B(path_a, path_b)
    print("path_a: {} contains path_b: {} = {}".format(path_a, path_b, test))
    assert(test is False)



def test_merge_simple_paths_containing_spacers():

    sg = Splice_graph()
    e1 = Exon("contig", 100, 200, 1)
    e1_ID = e1.get_id()
    sg._node_id_to_node[ e1_ID ] = e1

    e2 = Exon("contig", 300, 400, 1)
    e2_ID = e2.get_id()
    sg._node_id_to_node[ e2_ID ] = e2

    e3 = Exon("contig", 500, 600, 1)
    e3_ID = e3.get_id()
    sg._node_id_to_node[ e3_ID ] = e3

    e4 = Exon("contig", 700, 800, 1)
    e4_ID = e4.get_id()
    sg._node_id_to_node[ e4_ID ] = e4

    e5 = Exon("contig", 900, 1000, 1)
    e5_ID = e5.get_id()
    sg._node_id_to_node[ e5_ID ] = e5
    

    sp1 = [e1_ID, e2_ID, SPACER, e3_ID]
    sp2 = [e1_ID, SPACER, e2_ID, SPACER, e3_ID, SPACER, e5_ID]

    conv_sp1 = _convert_path_to_nodes_with_coords_list(sg, sp1)
    conv_sp2 = _convert_path_to_nodes_with_coords_list(sg, sp2)

    #print(str(conv_sp1))
    #print(str(conv_sp2))

    # mewrge them:
    merged = merge_simple_paths_containing_spacers(sg, sp1, sp2)
    print(str(merged))

    assert (merged == [['E:1', 100, 200], ['???', 201, 299], ['E:2', 300, 400], ['???', 401, 499], ['E:3', 500, 600], ['???', 601, 899], ['E:5', 900, 1000]] )

    
