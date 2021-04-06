

function sleep(interval){
    return new Promise(resolve => setTimeout(resolve,interval));
}


export class ActiveConnection{
    constructor(room_id, name){
        this.name = name;
        this.room_id = room_id;
        this.ws = new WebSocket(`ws://localhost:8500`);
        
        this.ws.onopen = async (e) =>{
            await this.sendOffer();
        }

        this.ws.onmessage = this.onWSMessage.bind(this);

        this.pc = new RTCPeerConnection();
        
        // This is required even if you don't use it. otherwise ICE wont be collected
        this.pc.createDataChannel("chat",{ordered: true}); 
        this.pc.ontrack = e =>{
            document.getElementById('audio').srcObject = e.streams[0];
        }


        this.pc.onicegatheringstatechange = e =>{
            console.log(this.pc.iceConnectionState);
        }
    }

    async onWSMessage(e) {
        let data = JSON.parse(e.data);
        if(data.type === 'answer'){
            await this.pc.setRemoteDescription({type:"answer", sdp: data.sdp});
            return;
        }
    }



    async sendOffer(){
        let offer = await this.pc.createOffer();
        await this.pc.setLocalDescription(offer);
        
        // Block till all ICE is gathered
        while(this.pc.iceGatheringState !== 'complete')
            await sleep(500);

        let constraints = {
            video: false,
            audio : true
        }

        let stream = await navigator.mediaDevices.getUserMedia(constraints);
        stream.getAudioTracks().forEach((track)=>{
            this.pc.addTrack(track, stream);
        });


        this.ws.send(JSON.stringify({
            name:this.name, 
            sdp: this.pc.localDescription,
            room_id : this.room_id,
        }));

    }
}

