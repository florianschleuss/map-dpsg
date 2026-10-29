def choose_promotions(mode,total_capacity,limits,occupied,waiting,total_occupied=None):
    """Pick eligible queued IDs in chronological order without mutating the inputs."""
    counts=dict(occupied)
    used=sum(counts.values()) if total_occupied is None else total_occupied
    selected=[]
    for registration_id,slot_id in waiting:
        if slot_id not in limits: continue
        if mode=='shared':
            if used>=total_capacity: break
        elif mode!='unlimited' and counts.get(slot_id,0)>=limits[slot_id]: continue
        selected.append(registration_id)
        counts[slot_id]=counts.get(slot_id,0)+1;used+=1
    return selected
